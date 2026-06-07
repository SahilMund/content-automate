"""
Telegram bot — trigger and approval interface.

Commands:
  /start       → asks for a topic, then runs the pipeline
  /auto_start  → auto-picks a topic and runs the pipeline

After the pipeline finishes a preview is sent with inline buttons:
  [LinkedIn] [Instagram] [Post All] [Post Reel] [LinkedIn Video] [Skip]
"""
import asyncio
import html
import logging
import os
import random
import re

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

load_dotenv()

from config import TOPICS
from graph.graph import app as pipeline
from graph.state import AgentState
from tools.poster import (
    post_reel_to_instagram,
    post_to_instagram,
    post_to_linkedin,
    post_video_to_linkedin,
)
from tools.progress import set_callback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WAITING_FOR_TOPIC = 1

# Keyed by chat_id — holds the last pipeline result until the user taps a button
_pending: dict[int, AgentState] = {}


# ── Helpers ──────────────────────────────────────────────────

def _extract(brief: str, section: str) -> str:
    m = re.search(rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)", brief, re.DOTALL)
    return m.group(1).strip() if m else ""


def _build_preview(result: AgentState) -> str:
    brief = result["content_brief"]
    topic = result["topic"]
    score = result["quality_score"]
    has_video = bool(result.get("video_path"))

    linkedin   = _extract(brief, "LinkedIn Post")
    instagram  = _extract(brief, "Instagram Caption")

    lines = [
        f"✅ <b>Research done!</b>  Quality: <b>{score}/10</b>",
        f"Topic: <code>{html.escape(topic)}</code>",
        f"🎬 <b>Video:</b> {'ready' if has_video else 'not generated'}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💼 <b>LinkedIn</b> <i>(preview)</i>",
        html.escape(linkedin[:500]) + ("…" if len(linkedin) > 500 else ""),
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📸 <b>Instagram</b> <i>(preview)</i>",
        html.escape(instagram[:300]) + ("…" if len(instagram) > 300 else ""),
    ]
    return "\n".join(lines)


def _approval_keyboard(has_video: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("💼 LinkedIn",     callback_data="post_linkedin"),
            InlineKeyboardButton("📸 Instagram",    callback_data="post_instagram"),
        ],
        [InlineKeyboardButton("🚀 Post All",        callback_data="post_all")],
    ]
    if has_video:
        rows.append([
            InlineKeyboardButton("🎬 Post Reel",        callback_data="post_reel"),
            InlineKeyboardButton("🎬 LinkedIn Video",    callback_data="post_linkedin_video"),
        ])
    rows.append([InlineKeyboardButton("⏭️ Skip", callback_data="skip")])
    return InlineKeyboardMarkup(rows)


_SENTINEL = object()


def _run_pipeline_sync(topic: str, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> AgentState:
    """Runs in a thread. Wires progress → queue, invokes the graph, puts sentinel when done."""
    def progress(msg: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, msg)

    set_callback(progress)
    try:
        initial: AgentState = {
            "topic": topic,
            "raw_research": "",
            "structured_brief": "",
            "content_brief": "",
            "images": [],
            "image_urls": [],
            "quality_score": 0.0,
            "retry_count": 0,
            "video_path": None,
            "error": None,
        }
        return pipeline.invoke(initial)
    finally:
        set_callback(None)
        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)


async def _consume_progress(queue: asyncio.Queue, status_msg) -> None:
    """Reads progress strings from the queue and edits the Telegram message live."""
    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        try:
            await status_msg.edit_text(item, parse_mode="HTML")
        except Exception:
            pass  # ignore flaky edits (e.g. message not modified)


async def _run_and_preview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topic: str,
    status_msg,
) -> None:
    """Run pipeline with live progress updates, then show approval preview."""
    try:
        await status_msg.edit_text(
            f"⏳ Starting pipeline for <b>{html.escape(topic)}</b>…", parse_mode="HTML"
        )

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        pipeline_task = asyncio.create_task(
            asyncio.to_thread(_run_pipeline_sync, topic, queue, loop)
        )
        await _consume_progress(queue, status_msg)
        result = await pipeline_task

        if result.get("error"):
            await status_msg.edit_text(f"❌ Error: {html.escape(result['error'])}")
            return

        chat_id = update.effective_chat.id
        _pending[chat_id] = result

        has_video = bool(result.get("video_path"))
        await status_msg.edit_text(
            _build_preview(result),
            parse_mode="HTML",
            reply_markup=_approval_keyboard(has_video=has_video),
        )
    except Exception as e:
        log.exception("Pipeline failed")
        await status_msg.edit_text(f"❌ Pipeline error: {html.escape(str(e))}")


# ── /auto-start ──────────────────────────────────────────────

async def auto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = random.choice(TOPICS)
    msg = await update.message.reply_text(
        f"🎯 Auto-picked topic: <b>{html.escape(topic)}</b>\nStarting pipeline…",
        parse_mode="HTML",
    )
    await _run_and_preview(update, context, topic, msg)


# ── /start (conversation: ask for topic) ────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    topics_list = " · ".join(TOPICS)
    await update.message.reply_text(
        "👋 What topic should I research?\n\n"
        f"<i>Configured topics: {html.escape(topics_list)}</i>\n\n"
        "Type any topic or pick from the list above.",
        parse_mode="HTML",
    )
    return WAITING_FOR_TOPIC


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Please enter a topic name.")
        return WAITING_FOR_TOPIC

    msg = await update.message.reply_text(
        f"⏳ Researching <b>{html.escape(topic)}</b>…", parse_mode="HTML"
    )
    await _run_and_preview(update, context, topic, msg)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Send /start or /auto-start to try again.")
    return ConversationHandler.END


# ── Approval callbacks ───────────────────────────────────────

_PLATFORM_LABELS = {
    "post_linkedin":       "LinkedIn 💼",
    "post_instagram":      "Instagram 📸",
    "post_all":            "LinkedIn & Instagram 🚀",
    "post_reel":           "Instagram Reel 🎬",
    "post_linkedin_video": "LinkedIn Video 🎬",
}


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    action  = query.data

    if action == "skip":
        _pending.pop(chat_id, None)
        await query.edit_message_text("⏭️ Skipped. Send /start or /auto-start to go again.")
        return

    result = _pending.get(chat_id)
    if not result:
        await query.edit_message_text("⚠️ Session expired. Run /start or /auto_start again.")
        return

    platform = _PLATFORM_LABELS.get(action, action)
    await query.edit_message_text(
        f"🚀 <b>Posting to {html.escape(platform)}…</b>", parse_mode="HTML"
    )

    brief  = result["content_brief"]
    images = result["images"]
    image  = images[0] if images else None
    video      = result.get("video_path")
    urls   = []
    errors = []

    if action in ("post_linkedin", "post_all"):
        li_text = _extract(brief, "LinkedIn Post")
        try:
            url = await asyncio.to_thread(post_to_linkedin, li_text, image)
            urls.append(f"💼 <a href='{url}'>Posted to LinkedIn</a>")
        except Exception as e:
            log.exception("LinkedIn post failed")
            errors.append(f"💼 LinkedIn failed: {html.escape(str(e))}")

    if action in ("post_instagram", "post_all"):
        insta_caption = _extract(brief, "Instagram Caption")
        if not image:
            errors.append("📸 Instagram skipped — no image available")
        else:
            try:
                url = await asyncio.to_thread(post_to_instagram, insta_caption, image)
                urls.append(f"📸 <a href='{url}'>Posted to Instagram</a>")
            except Exception as e:
                log.exception("Instagram post failed")
                errors.append(f"📸 Instagram failed: {html.escape(str(e))}")

    if action == "post_reel":
        reel_caption = _extract(brief, "Instagram Caption")
        if not video:
            errors.append("🎬 Reel skipped — no video available")
        else:
            try:
                url = await asyncio.to_thread(post_reel_to_instagram, reel_caption, video)
                urls.append(f"🎬 <a href='{url}'>Posted Reel to Instagram</a>")
            except Exception as e:
                log.exception("Instagram Reel failed")
                errors.append(f"🎬 Reel failed: {html.escape(str(e))}")

    if action == "post_linkedin_video":
        li_text = _extract(brief, "LinkedIn Post")
        if not video:
            errors.append("🎬 LinkedIn Video skipped — no video available")
        else:
            try:
                url = await asyncio.to_thread(post_video_to_linkedin, li_text, video)
                urls.append(f"🎬 <a href='{url}'>Posted Video to LinkedIn</a>")
            except Exception as e:
                log.exception("LinkedIn video failed")
                errors.append(f"🎬 LinkedIn video failed: {html.escape(str(e))}")

    lines = ["✅ <b>Done!</b>"] + urls + errors
    _pending.pop(chat_id, None)
    await query.edit_message_text("\n".join(lines), parse_mode="HTML")


# ── Error handler ────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, (TimedOut, NetworkError)):
        # Transient — log and move on, no need to alert the user
        log.warning("Transient Telegram error: %s", err)
        return
    log.exception("Unhandled exception in update handler")
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Something went wrong. Try /start or /auto_start again."
        )


# ── App assembly ─────────────────────────────────────────────

def build_app() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    # Increase timeouts — default 5 s is too short under any latency
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = Application.builder().token(token).request(request).build()

    app.add_error_handler(error_handler)

    # /start conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAITING_FOR_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topic)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # /auto_start (not a conversation — fires immediately)
    app.add_handler(CommandHandler("auto_start", auto_start))

    # inline button taps
    app.add_handler(CallbackQueryHandler(handle_approval))

    return app
