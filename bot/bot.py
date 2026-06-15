"""
Telegram bot — trigger, live-progress, approval, and feedback interface.

Commands:
  /start       → asks for a topic, then runs the pipeline
  /auto_start  → auto-picks a topic and runs the pipeline

Voice message → transcribe via Groq Whisper, use as topic.

Pipeline runs with a live checklist:
  ✅ done  ⏳ active  ── pending

After pipeline:
  1. Carousel album (7 PNGs)
  2. Video (if generated)
  3. Preview + approval buttons  [LinkedIn] [Instagram] [Post All] [Skip]
  4. Feedback prompt — reply to regenerate with your notes
"""

import asyncio
import html
import logging
import os
import random
import re
import tempfile

from dotenv import load_dotenv
from groq import Groq
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
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

_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

from config import TOPICS
from graph.graph import app as pipeline
from graph.state import AgentState
from tools.poster import (
    post_carousel_to_instagram,
    post_reel_to_instagram,
    post_to_linkedin,
    post_video_to_linkedin,
)
from tools.progress import set_callback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WAITING_FOR_TOPIC = 1

# ── State dicts ───────────────────────────────────────────────
# last pipeline result per chat
_pending: dict[int, AgentState] = {}
# session metadata per chat: {topic, feedback_msg_id}
_session: dict[int, dict] = {}


# ── Live-checklist helpers ────────────────────────────────────

PIPELINE_STEPS = [
    ("research",   "🔍  Research"),
    ("analysis",   "✍️   Write content"),
    ("validation", "🔎  Validate quality"),
    ("carousel",   "🎨  Generate slides"),
    ("video",      "🎬  Create video"),
]


def _checklist(topic: str, done: set[str], active: str | None, note: str = "") -> str:
    lines = [f"⏳ <b>{html.escape(topic)}</b>\n"]
    for key, label in PIPELINE_STEPS:
        if key in done:
            lines.append(f"✅  {label}")
        elif key == active:
            lines.append(f"⏳  {label}…")
        else:
            lines.append(f"──  {label}")
    if note:
        lines.append(f"\n<i>{html.escape(note)}</i>")
    return "\n".join(lines)


def _checklist_done(topic: str) -> str:
    lines = [f"✅ <b>{html.escape(topic)}</b> — done!\n"]
    for _, label in PIPELINE_STEPS:
        lines.append(f"✅  {label}")
    return "\n".join(lines)


# ── Pipeline runner ───────────────────────────────────────────

_SENTINEL = object()


def _run_pipeline_sync(
    topic: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    user_feedback: str = "",
    raw_content: str = "",
) -> AgentState:
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
            "validation_feedback": "",
            "validation_attempts": 0,
            "carousel_paths": [],
            "user_feedback": user_feedback,
            "raw_content": raw_content,
        }
        return pipeline.invoke(initial)
    finally:
        set_callback(None)
        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)


async def _consume_progress(
    queue: asyncio.Queue,
    status_msg,
    topic: str,
) -> None:
    """Parse STEP:/DONE:/NOTE: markers and edit the message as a live checklist."""
    done: set[str] = set()
    active: str | None = None
    note: str = ""

    # Show the initial blank checklist immediately
    try:
        await status_msg.edit_text(_checklist(topic, done, None), parse_mode="HTML")
    except Exception:
        pass

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        if not isinstance(item, str):
            continue

        if item.startswith("STEP:"):
            active = item[5:]
            note = ""
        elif item.startswith("DONE:"):
            done.add(item[5:])
            active = None
        elif item.startswith("NOTE:"):
            note = item[5:]
        else:
            continue  # ignore legacy free-text emits

        try:
            await status_msg.edit_text(
                _checklist(topic, done, active, note), parse_mode="HTML"
            )
        except Exception:
            pass


# ── Preview + approval ────────────────────────────────────────

def _extract(brief: str, section: str) -> str:
    m = re.search(rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)", brief, re.DOTALL)
    return m.group(1).strip() if m else ""


def _build_preview(result: AgentState) -> str:
    brief     = result["content_brief"]
    topic     = result["topic"]
    score     = result["quality_score"]
    has_video = bool(result.get("video_path"))
    slides    = len(result.get("carousel_paths", []))

    linkedin  = _extract(brief, "LinkedIn Post")
    instagram = _extract(brief, "Instagram Caption")

    lines = [
        f"✅ <b>Pipeline complete!</b>  Quality: <b>{score}/10</b>",
        f"Topic: <code>{html.escape(topic)}</code>",
        f"🎨 Slides: {slides}   🎬 Video: {'ready' if has_video else '—'}",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💼 <b>LinkedIn</b> <i>(preview)</i>",
        html.escape(linkedin[:400]) + ("…" if len(linkedin) > 400 else ""),
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📸 <b>Instagram</b> <i>(preview)</i>",
        html.escape(instagram[:250]) + ("…" if len(instagram) > 250 else ""),
    ]
    return "\n".join(lines)


def _approval_keyboard(has_video: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("💼 LinkedIn",  callback_data="post_linkedin"),
            InlineKeyboardButton("📸 Instagram", callback_data="post_instagram"),
        ],
        [InlineKeyboardButton("🚀 Post All", callback_data="post_all")],
    ]
    if has_video:
        rows.append([
            InlineKeyboardButton("🎬 Post Reel",       callback_data="post_reel"),
            InlineKeyboardButton("🎬 LinkedIn Video",  callback_data="post_linkedin_video"),
        ])
    rows.append([InlineKeyboardButton("⏭️ Skip", callback_data="skip")])
    return InlineKeyboardMarkup(rows)


async def _send_carousel_and_video(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    result: AgentState,
) -> None:
    """Send carousel PNG album + video file to the chat."""
    carousel = result.get("carousel_paths", [])
    if carousel:
        try:
            media = [InputMediaPhoto(media=open(p, "rb")) for p in carousel[:10]]
            await context.bot.send_media_group(chat_id=chat_id, media=media)
        except Exception as e:
            log.warning("Could not send carousel album: %s", e)

    video = result.get("video_path")
    if video and os.path.isfile(video):
        try:
            with open(video, "rb") as vf:
                await context.bot.send_video(
                    chat_id=chat_id, video=vf, caption="🎬 Generated video"
                )
        except Exception as e:
            log.warning("Could not send video: %s", e)


# ── Main pipeline runner (used by all entry points) ───────────

async def _run_and_preview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    topic: str,
    status_msg,
    user_feedback: str = "",
    raw_content: str = "",
) -> None:
    """Run pipeline with live checklist, then send slides/video/preview."""
    try:
        loop  = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        pipeline_task = asyncio.create_task(
            asyncio.to_thread(_run_pipeline_sync, topic, queue, loop, user_feedback, raw_content)
        )
        await _consume_progress(queue, status_msg, topic)
        result = await pipeline_task

        if result.get("error"):
            await status_msg.edit_text(f"❌ Error: {html.escape(result['error'])}")
            return

        chat_id = update.effective_chat.id
        _pending[chat_id] = result

        # 1 — mark checklist done
        await status_msg.edit_text(_checklist_done(topic), parse_mode="HTML")

        # 2 — send carousel images + video
        await _send_carousel_and_video(context, chat_id, result)

        # 3 — send preview + approval buttons (new message)
        has_video = bool(result.get("video_path"))
        preview_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=_build_preview(result),
            parse_mode="HTML",
            reply_markup=_approval_keyboard(has_video=has_video),
        )

        # 4 — send feedback prompt; user can reply to regenerate
        fb_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "💬 <b>Not happy with the output?</b>\n"
                "Reply to this message with your feedback and I'll regenerate.\n"
                "<i>e.g. 'Make the hook more punchy' or 'Focus on React 19 specifically'</i>"
            ),
            parse_mode="HTML",
        )
        _session[chat_id] = {
            "topic": topic,
            "feedback_msg_id": fb_msg.message_id,
        }

    except Exception as e:
        err_str = str(e)
        if err_str.startswith("RATE_LIMIT:"):
            # Clean rate-limit message — don't log a full traceback
            friendly = err_str[len("RATE_LIMIT:"):]
            log.warning("Rate limit hit: %s", friendly)
            await status_msg.edit_text(
                f"⏳ <b>Rate limit hit</b>\n{html.escape(friendly)}\n\n"
                "Try again once the limit resets.",
                parse_mode="HTML",
            )
        else:
            log.exception("Pipeline failed")
            await status_msg.edit_text(
                f"❌ <b>Pipeline error</b>\n<code>{html.escape(err_str[:300])}</code>",
                parse_mode="HTML",
            )


# ── /auto_start ───────────────────────────────────────────────

async def auto_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = random.choice(TOPICS)
    msg = await update.message.reply_text(
        f"🎯 Auto-picked: <b>{html.escape(topic)}</b>", parse_mode="HTML"
    )
    await _run_and_preview(update, context, topic, msg)


# ── /start conversation ───────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    topics_list = " · ".join(TOPICS[:6])
    await update.message.reply_text(
        "👋 <b>What topic should I create content for?</b>\n\n"
        "Type any developer topic — or paste a URL / article text and I'll use that as source.\n\n"
        f"<i>e.g. {html.escape(topics_list)}…</i>",
        parse_mode="HTML",
    )
    return WAITING_FOR_TOPIC


async def receive_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Please enter a topic name.")
        return WAITING_FOR_TOPIC
    msg = await update.message.reply_text(
        f"⏳ Starting pipeline for <b>{html.escape(topic)}</b>…", parse_mode="HTML"
    )
    await _run_and_preview(update, context, topic, msg)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Send /start or /auto_start to try again.")
    return ConversationHandler.END


# ── Voice message ─────────────────────────────────────────────

async def receive_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status = await update.message.reply_text("🎙️ Transcribing…")
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await voice_file.download_to_drive(tmp_path)

        with open(tmp_path, "rb") as audio:
            transcription = await asyncio.to_thread(
                lambda: _groq.audio.transcriptions.create(
                    file=(os.path.basename(tmp_path), audio),
                    model="whisper-large-v3",
                )
            )
        os.unlink(tmp_path)
    except Exception as e:
        log.exception("Voice transcription failed")
        await status.edit_text(f"❌ Transcription failed: {html.escape(str(e))}")
        return

    topic = transcription.text.strip()
    if not topic:
        await status.edit_text("❌ Couldn't understand the voice message. Try again.")
        return

    await status.edit_text(
        f"🎙️ Heard: <b>{html.escape(topic)}</b>", parse_mode="HTML"
    )
    await _run_and_preview(update, context, topic, status)


# ── URL / pasted-content handler ─────────────────────────────

_URL_RE = re.compile(r"^https?://\S+", re.IGNORECASE)


async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a URL or long pasted text — use directly as source content for the pipeline."""
    text = (update.message.text or "").strip()
    if not text:
        return

    is_url = bool(_URL_RE.match(text))
    is_long = len(text) > 350 and not is_url

    if not is_url and not is_long:
        return  # short plain text — not our concern

    # Derive a topic name
    if is_url:
        # strip query params, take last path segment
        path = text.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        path = re.sub(r"[^a-zA-Z0-9\-_]", " ", path).strip()
        topic = path[:60] if path else "article"
        source_label = "URL"
    else:
        # First non-empty line, trimmed
        first_line = next((l.strip() for l in text.splitlines() if l.strip()), text[:60])
        topic = first_line[:60]
        source_label = "content"

    msg = await update.message.reply_text(
        f"📥 Got the {source_label}! Building post…\n"
        f"<i>{html.escape(topic[:80])}</i>",
        parse_mode="HTML",
    )
    await _run_and_preview(update, context, topic, msg, raw_content=text)


# ── Feedback reply handler ────────────────────────────────────

async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a reply to the feedback prompt message → regenerate with user notes."""
    chat_id = update.effective_chat.id
    session = _session.get(chat_id, {})
    feedback_msg_id = session.get("feedback_msg_id")

    reply = update.message.reply_to_message
    if not reply or not feedback_msg_id or reply.message_id != feedback_msg_id:
        return  # not a reply to our feedback prompt — ignore

    feedback = update.message.text.strip()
    if not feedback:
        return

    topic = session.get("topic", "")
    msg = await update.message.reply_text(
        f"📝 Got it! Regenerating <b>{html.escape(topic)}</b> with your feedback…",
        parse_mode="HTML",
    )
    # Clear old session so we don't loop on the same feedback_msg_id
    _session.pop(chat_id, None)
    await _run_and_preview(update, context, topic, msg, user_feedback=feedback)


# ── Approval callbacks ────────────────────────────────────────

_PLATFORM_LABELS = {
    "post_linkedin":       "LinkedIn 💼",
    "post_instagram":      "Instagram 📸",
    "post_all":            "LinkedIn & Instagram 🚀",
    "post_reel":           "Instagram Reel 🎬",
    "post_linkedin_video": "LinkedIn Video 🎬",
}


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query  = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    action  = query.data

    if action == "skip":
        _pending.pop(chat_id, None)
        await query.edit_message_text("⏭️ Skipped. Send /start or /auto_start to go again.")
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
    video  = result.get("video_path")
    urls, errors = [], []

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
        carousel = result.get("carousel_paths", [])
        if not carousel:
            errors.append("📸 Instagram skipped — no carousel slides available")
        else:
            try:
                url = await asyncio.to_thread(
                    post_carousel_to_instagram, insta_caption, carousel
                )
                urls.append(f"📸 <a href='{url}'>Posted carousel to Instagram</a>")
            except Exception as e:
                log.exception("Instagram carousel post failed")
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
                log.exception("Reel post failed")
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

    _pending.pop(chat_id, None)
    await query.edit_message_text(
        "\n".join(["✅ <b>Done!</b>"] + urls + errors), parse_mode="HTML"
    )


# ── Error handler ─────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, (TimedOut, NetworkError)):
        log.warning("Transient Telegram error: %s", err)
        return
    log.exception("Unhandled exception in update handler")
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Something went wrong. Try /start or /auto_start again."
        )


# ── App assembly ──────────────────────────────────────────────

_BOT_COMMANDS = [
    BotCommand("start",      "Enter a topic and generate content"),
    BotCommand("auto_start", "Auto-pick a topic and generate content"),
    BotCommand("cancel",     "Cancel current operation"),
]


async def _post_init(app: "Application") -> None:
    await app.bot.set_my_commands(_BOT_COMMANDS)
    log.info("Bot commands registered")


def build_app() -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    app = Application.builder().token(token).request(request).post_init(_post_init).build()
    app.add_error_handler(error_handler)

    # /start conversation (ask for topic)
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={WAITING_FOR_TOPIC: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topic)
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    # /auto_start — pick a random topic
    app.add_handler(CommandHandler("auto_start", auto_start))

    # Voice → Whisper → pipeline
    app.add_handler(MessageHandler(filters.VOICE, receive_voice))

    # URL or long pasted text → pipeline (group 0, runs before feedback check)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_content),
        group=0,
    )

    # Feedback reply — must come after ConversationHandler (group=1)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback),
        group=1,
    )

    # Inline button taps (approval)
    app.add_handler(CallbackQueryHandler(handle_approval))

    return app
