"""
Carousel generator — @the.undefined.parts brand identity.

Output: 5-7 × 1080×1350 PNG slides (4:5 Instagram portrait)
Design: dark grainy background, purple accent (#9B5DE5), Barlow Condensed.
Slides: driven by ## Slide Plan in content_brief; flexible per content type.

Slide types: cover | hook | context | bullets | code | cards | quote | cta
"""

import re
from datetime import date
from html import escape as _esc
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import OUTPUTS_DIR

W, H = 1080, 1350

PURPLE    = "#9B5DE5"
WHITE     = "#FFFFFF"
GRAY      = "#6b6b7e"
CODE_BG   = "#0c0c14"

GOOGLE_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Barlow+Condensed:ital,wght@0,400;0,500;0,600;0,700;0,800;0,900;"
    "1,400&family=JetBrains+Mono:wght@400;500&display=swap"
)
HLJS_CSS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css"
HLJS_JS  = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"


# ── Slide plan parser ──────────────────────────────────────────────────────────

def _parse_slide_plan(brief: str) -> list[dict]:
    """Parse ## Slide Plan section into ordered list of slide specs."""
    m = re.search(r"## Slide Plan\n(.*?)(?=\n## |\Z)", brief, re.DOTALL)
    if not m:
        return []

    plan_text = m.group(1)
    raw_blocks = re.split(r"(?m)^SLIDE:\s*", plan_text)

    slides = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.splitlines()
        slide_type = lines[0].strip().lower()
        spec: dict = {"type": slide_type, "items": []}
        code_lines: list[str] = []
        in_code = False

        for line in lines[1:]:
            stripped = line.strip()
            if stripped.upper() == "CODE:":
                in_code = True
                continue
            if in_code:
                code_lines.append(line)
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip().upper()
                val = val.strip()
                if key == "ITEM":
                    spec["items"].append(val)
                else:
                    spec[key.lower()] = val

        if code_lines:
            spec["code"] = "\n".join(code_lines).strip()

        if slide_type:
            slides.append(spec)

    return slides


# ── Fallback: derive slide plan from existing brief sections ───────────────────

_VERBOSE_RE = re.compile(
    r"^(the specific concept (this post is about is|we are exploring is?)|"
    r"this post (focuses on|is about)|we are (exploring|diving into)|"
    r"today (we|i)'?(m| am) (exploring|covering|talking about))[:\s]*",
    re.IGNORECASE,
)
_EMOJI_RE = re.compile(
    r"^([\U0001F300-\U0001FAFF\U00002600-\U000027BF"
    r"\U00002B00-\U00002BFF\U0001F000-\U0001F9FF]+\s*)"
)


def _sec(brief: str, name: str) -> str:
    m = re.search(rf"## {re.escape(name)}\n(.*?)(?=\n## |\Z)", brief, re.DOTALL)
    return m.group(1).strip() if m else ""


def _fallback_slides(topic: str, brief: str) -> list[dict]:
    caption  = _sec(brief, "Instagram Caption")
    code_sec = _sec(brief, "Code Snippet")
    angle    = _VERBOSE_RE.sub("", _sec(brief, "Chosen Angle")).strip().rstrip(".") or topic

    # concept / tagline
    angle_clean = re.sub(r"^the\s+", "", angle, flags=re.IGNORECASE)
    cm = re.match(r"(.+?)(?:\s+(?:for|in|to|that|which|using|by)\b.*)?$", angle_clean, re.IGNORECASE | re.DOTALL)
    concept = cm.group(1).strip() if cm else angle_clean
    tm = re.search(r"\b(?:for|to|that)\s+(.+)$", angle, re.IGNORECASE)
    tagline = (tm.group(1).strip() if tm else angle)[:70]

    # hook
    first = _EMOJI_RE.sub("", caption.split("\n")[0]).strip() if caption else ""
    hm = re.match(r"^(.+?[!?])", first)
    hook = hm.group(1) if hm else first[:80]

    # analogy
    am = re.search(r"(Enter .+?[—–].+?)(?:\.|$)", caption, re.MULTILINE)
    analogy = am.group(1).strip() if am else ""

    # benefits
    benefits = [b.strip() for b in re.findall(r"✅\s*(.+)", caption) if b.strip()]

    # definition bullets
    defn: list[str] = []
    if hook:
        defn.append(hook.rstrip("!?."))
    ev = re.search(r"(Ever wondered[^?\n]+\?)", caption, re.IGNORECASE)
    if ev:
        defn.append(ev.group(1))
    if analogy:
        defn.append(analogy)
    for b in benefits:
        if len(defn) >= 3:
            break
        defn.append(b)
    defn = defn[:3] or [angle]

    # code
    lm = re.search(r"Language:\s*(\w+)", code_sec, re.IGNORECASE)
    language = lm.group(1).lower() if lm else "javascript"
    snippet_m = re.search(r"```\w*\n(.*?)```", code_sec, re.DOTALL)
    snippet = snippet_m.group(1).strip() if snippet_m else ""

    # engagement question
    qm = re.search(r"([A-Z][^?!\n]{10,}?\?)\s*👇", caption)
    if not qm:
        qs = re.findall(r"[A-Z][^?!\n]{8,}?\?", caption)
        question = qs[-1].strip() if qs else "How do you handle this in your projects?"
    else:
        question = qm.group(1).strip()

    # takeaways: analogy + benefits
    take_items = ([analogy] if analogy else []) + benefits
    take_items = take_items[:3] or ["Simple to learn", "Production ready", "Well-supported"]

    specs: list[dict] = [
        {"type": "cover",   "concept": concept, "tagline": tagline},
        {"type": "hook",    "concept": concept},
        {"type": "bullets", "title": "The Gist", "items": defn},
    ]
    if snippet and snippet.lower() != "n/a":
        specs.append({"type": "code", "language": language, "code": snippet})
    specs += [
        {"type": "bullets", "title": "Common Use Cases",
         "items": benefits[:4] or ["Cleaner code", "Better performance", "Easier to maintain"]},
        {"type": "cards",   "title": "Key Takeaways", "items": take_items},
        {"type": "cta",     "question": question},
    ]
    return specs


# ── Shared shell ───────────────────────────────────────────────────────────────

_LOGO_SVG = (
    f'<svg width="26" height="26" viewBox="0 0 26 26" fill="none">'
    f'<line x1="3.5" y1="3.5" x2="22.5" y2="22.5" stroke="{PURPLE}" stroke-width="3.2" stroke-linecap="round"/>'
    f'<line x1="22.5" y1="3.5" x2="3.5" y2="22.5" stroke="{PURPLE}" stroke-width="3.2" stroke-linecap="round"/>'
    f'</svg>'
)

_NOISE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;">'
    '<filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.72" numOctaves="4" '
    'stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>'
    '<rect width="100%" height="100%" filter="url(#g)" opacity="0.055"/></svg>'
)

_BASE_CSS = f"""
* {{margin:0;padding:0;box-sizing:border-box;}}
body {{
  width:{W}px;height:{H}px;overflow:hidden;
  background:radial-gradient(ellipse at 50% 38%,#1e1e24 0%,#111214 52%,#0a0a0c 100%);
  font-family:'Barlow Condensed','Arial Narrow',sans-serif;
  color:{WHITE};position:relative;
}}
.slide {{
  position:relative;z-index:1;width:100%;height:100%;
  padding:52px 64px 50px;display:flex;flex-direction:column;
}}
.hdr {{display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}}
.logo-g {{display:flex;align-items:center;gap:10px;}}
.logo-t {{font-size:18px;font-weight:500;letter-spacing:0.02em;color:{WHITE};}}
.nav {{
  width:44px;height:44px;border-radius:50%;border:1.5px solid #505060;
  display:flex;align-items:center;justify-content:center;
  color:#9999aa;font-size:20px;flex-shrink:0;
}}
.body {{flex:1;display:flex;flex-direction:column;min-height:0;}}
.foot {{
  flex-shrink:0;padding-top:14px;font-size:17px;font-weight:400;
  font-style:italic;color:{GRAY};letter-spacing:0.03em;
}}
.slide-title {{
  font-size:50px;font-weight:800;text-transform:uppercase;
  letter-spacing:0.02em;color:{WHITE};flex-shrink:0;line-height:1.0;
}}
.section-label {{
  font-size:26px;font-weight:600;text-transform:uppercase;letter-spacing:0.14em;
  color:{PURPLE};border-bottom:1px solid rgba(155,93,229,0.25);
  padding-bottom:14px;flex-shrink:0;
}}
"""


def _wrap(body: str, series: str, extra_css: str = "", extra_head: str = "") -> str:
    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link href="{GOOGLE_FONTS}" rel="stylesheet">'
        f'{extra_head}'
        f'<style>{_BASE_CSS}{extra_css}</style></head><body>'
        f'{_NOISE_SVG}'
        f'<div class="slide">'
        f'  <div class="hdr">'
        f'    <div class="logo-g">{_LOGO_SVG}<span class="logo-t">the.undefined.parts</span></div>'
        f'    <div class="nav">&#x2192;</div>'
        f'  </div>'
        f'  <div class="body">{body}</div>'
        f'  <div class="foot">{_esc(series)}</div>'
        f'</div></body></html>'
    )


# ── Slide renderers ────────────────────────────────────────────────────────────

def _cover_font(n: int) -> int:
    if n <= 8:  return 148
    if n <= 12: return 130
    if n <= 17: return 112
    if n <= 24: return 92
    return 74


def _r_cover(spec: dict, series: str) -> str:
    concept = spec.get("concept", "Concept").upper()
    tagline = spec.get("tagline", "").upper()
    fsize   = _cover_font(len(concept))

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;padding-top:52px;">
  <div style="flex:1;">
    <div style="font-size:{fsize}px;font-weight:900;line-height:0.86;
                color:{PURPLE};letter-spacing:-0.02em;
                text-transform:uppercase;word-break:break-word;">{_esc(concept)}</div>
  </div>
  <div style="padding-bottom:36px;">
    <div style="font-size:52px;font-weight:800;line-height:1.05;
                color:{WHITE};text-transform:uppercase;letter-spacing:0.01em;">{_esc(tagline)}</div>
  </div>
</div>"""
    return _wrap(body, series)


def _r_hook(spec: dict, series: str) -> str:
    concept = spec.get("concept", "This Concept").upper()
    n = len(concept)
    fsize = 82 if n <= 14 else 68 if n <= 22 else 56

    deco = (
        f'<div style="margin-top:50px;position:relative;width:108px;height:72px;">'
        f'<div style="position:absolute;top:0;left:0;width:36px;height:36px;background:{PURPLE};"></div>'
        f'<div style="position:absolute;top:0;left:36px;width:36px;height:36px;background:{PURPLE};"></div>'
        f'<div style="position:absolute;top:36px;left:36px;width:36px;height:36px;background:{PURPLE};"></div>'
        f'</div>'
    )

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-top:16px;">
  <div style="font-size:64px;font-weight:800;color:{PURPLE};text-transform:uppercase;
              line-height:1.0;margin-bottom:4px;letter-spacing:0.01em;">LET ME TELL YOU</div>
  <div style="font-size:{fsize}px;font-weight:900;color:{WHITE};text-transform:uppercase;
              line-height:0.95;letter-spacing:0.01em;">WHAT IS THE<br>{_esc(concept)}?</div>
  {deco}
</div>"""
    return _wrap(body, series)


def _r_bullets(spec: dict, series: str) -> str:
    title = spec.get("title", "Key Points").upper()
    items = spec.get("items", [])[:4]

    bullets = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:16px;">'
        f'<span style="color:{PURPLE};font-size:36px;flex-shrink:0;line-height:1.2;margin-top:1px;">&#x273D;</span>'
        f'<span style="font-size:27px;font-weight:700;text-transform:uppercase;'
        f'line-height:1.32;color:{WHITE};">{_esc(b.upper())}</span>'
        f'</div>'
        for b in items
    )

    # Definition-style slides (gist/context/definition) get the subtle label treatment
    is_definition = spec.get("type") in ("definition",) or title in ("THE GIST", "GIST")

    if is_definition:
        body = f"""
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;
            padding-top:16px;padding-bottom:16px;gap:44px;">
  <div class="section-label">{_esc(title)}</div>
  <div style="display:flex;flex-direction:column;gap:36px;">{bullets}</div>
</div>"""
    else:
        body = f"""
<div style="flex:1;display:flex;flex-direction:column;padding-top:24px;
            padding-bottom:16px;gap:40px;">
  <div class="slide-title">{_esc(title)}</div>
  <div style="display:flex;flex-direction:column;gap:28px;">{bullets}</div>
</div>"""

    return _wrap(body, series)


def _r_code(spec: dict, series: str) -> str:
    snippet  = spec.get("code", spec.get("snippet", "")).strip()
    language = spec.get("language", "javascript").strip().lower()

    if not snippet or snippet.lower() == "n/a":
        return ""

    lines = snippet.split("\n")
    if len(lines) > 22:
        snippet = "\n".join(lines[:22]) + "\n…"

    extra_head = (
        f'<link rel="stylesheet" href="{HLJS_CSS}">'
        f'<script src="{HLJS_JS}"></script>'
    )
    extra_css = f"""
.code-box {{
  flex:1;background:{CODE_BG};border-radius:14px;
  padding:26px 28px;overflow:hidden;display:flex;flex-direction:column;min-height:0;
}}
.lang-lbl {{
  font-size:14px;color:#484860;font-family:'JetBrains Mono',monospace;
  margin-bottom:10px;text-transform:lowercase;flex-shrink:0;
}}
pre {{margin:0;overflow:hidden;flex:1;}}
code {{
  font-family:'JetBrains Mono',monospace !important;
  font-size:19px !important;line-height:1.55 !important;tab-size:2;
}}
.hljs {{background:transparent !important;padding:0 !important;}}
"""

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;padding-top:22px;gap:20px;">
  <div class="slide-title">HOW IT WORKS</div>
  <div class="code-box">
    <div class="lang-lbl">{_esc(language)}</div>
    <pre><code class="language-{_esc(language)}">{_esc(snippet)}</code></pre>
  </div>
</div>
<script>hljs.highlightAll();</script>"""
    return _wrap(body, series, extra_css=extra_css, extra_head=extra_head)


def _r_cards(spec: dict, series: str) -> str:
    title = spec.get("title", "Key Takeaways").upper()
    items = spec.get("items", [])[:3]

    cards = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:20px;padding:18px 22px;'
        f'background:rgba(155,93,229,0.07);border-radius:12px;border-left:3px solid {PURPLE};">'
        f'<span style="font-size:18px;font-weight:800;color:{PURPLE};flex-shrink:0;'
        f'line-height:1.6;letter-spacing:0.05em;margin-top:1px;">{i+1:02d}</span>'
        f'<span style="font-size:25px;font-weight:500;line-height:1.4;color:{WHITE};">{_esc(item)}</span>'
        f'</div>'
        for i, item in enumerate(items)
    )

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;padding-top:24px;
            padding-bottom:16px;gap:44px;">
  <div class="slide-title">{_esc(title)}</div>
  <div style="display:flex;flex-direction:column;gap:18px;">{cards}</div>
</div>"""
    return _wrap(body, series)


def _r_quote(spec: dict, series: str) -> str:
    quote       = spec.get("quote", "")
    attribution = spec.get("attribution", "")
    n = len(quote)
    qfsize = 56 if n <= 80 else 44 if n <= 140 else 36

    attr_html = (
        f'<div style="font-size:22px;color:{GRAY};font-weight:500;padding:0 8px;">'
        f'— {_esc(attribution)}</div>'
        if attribution else ""
    )

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:28px;
            padding:24px 0;">
  <div style="font-size:80px;color:{PURPLE};font-weight:900;line-height:0.8;opacity:0.35;">"</div>
  <div style="font-size:{qfsize}px;font-weight:700;line-height:1.25;color:{WHITE};
              font-style:italic;padding:0 8px;">{_esc(quote)}</div>
  {attr_html}
</div>"""
    return _wrap(body, series)


def _r_cta(spec: dict, series: str) -> str:
    question = spec.get("question", "What do you think?").upper()
    n = len(question)
    qfsize = 72 if n <= 28 else 58 if n <= 48 else 46

    geo = (
        f'<svg width="230" height="230" viewBox="0 0 230 230" fill="none" '
        f'style="position:absolute;top:0;right:-8px;opacity:0.14;pointer-events:none;">'
        f'<polygon points="115,8 222,195 8,195" stroke="{PURPLE}" stroke-width="1.5"/>'
        f'<polygon points="115,38 192,180 38,180" stroke="{PURPLE}" stroke-width="1"/>'
        f'<line x1="115" y1="8" x2="115" y2="195" stroke="{PURPLE}" stroke-width="1"/>'
        f'<line x1="8" y1="195" x2="222" y2="195" stroke="{PURPLE}" stroke-width="1.5"/>'
        f'<line x1="62" y1="102" x2="168" y2="102" stroke="{PURPLE}" stroke-width="0.8"/>'
        f'<circle cx="115" cy="8" r="3" fill="{PURPLE}"/>'
        f'<circle cx="8" cy="195" r="3" fill="{PURPLE}"/>'
        f'<circle cx="222" cy="195" r="3" fill="{PURPLE}"/>'
        f'</svg>'
    )

    body = f"""
<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;
            position:relative;padding-bottom:56px;">
  {geo}
  <div style="font-size:{qfsize}px;font-weight:900;line-height:0.94;color:{PURPLE};
              text-transform:uppercase;margin-bottom:34px;letter-spacing:0.01em;
              position:relative;z-index:1;">{_esc(question)}</div>
  <div style="font-size:60px;font-weight:900;line-height:0.94;color:{WHITE};
              text-transform:uppercase;letter-spacing:0.01em;position:relative;z-index:1;">
    FOLLOW FOR MORE<br>TECH INSIGHTS &#x1F680;
  </div>
</div>"""
    return _wrap(body, series)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _render_spec(spec: dict, series: str) -> str:
    t = spec.get("type", "")
    if t == "cover":                         return _r_cover(spec, series)
    if t == "hook":                          return _r_hook(spec, series)
    if t in ("bullets", "context"):          return _r_bullets(spec, series)
    if t == "code":                          return _r_code(spec, series)
    if t == "cards":                         return _r_cards(spec, series)
    if t == "quote":                         return _r_quote(spec, series)
    if t == "cta":                           return _r_cta(spec, series)
    return ""


def _series_label(brief: str, topic: str) -> str:
    m = re.search(r"## Chosen Angle\n(.+?)(?:\n|$)", brief)
    angle = m.group(1).strip() if m else topic
    lm = re.search(r"\b(JavaScript|TypeScript|Python|Rust|Go|Java|React|Next\.?js|Node|CSS|HTML|AI)\b", angle, re.IGNORECASE)
    lang = lm.group(1).title() if lm else "Tech"
    return f"Advanced {lang} Series"


# ── Public API ────────────────────────────────────────────────────────────────

def generate_carousel(topic: str, content_brief: str) -> list[str]:
    """Generate carousel slides from ## Slide Plan in content_brief. Returns PNG paths."""
    slide_specs = _parse_slide_plan(content_brief)
    if not slide_specs:
        print("[carousel] No Slide Plan found — using fallback parser")
        slide_specs = _fallback_slides(topic, content_brief)

    series  = _series_label(content_brief, topic)
    safe    = re.sub(r"[^a-z0-9_-]", "_", topic.lower())[:40]
    out_dir = Path(OUTPUTS_DIR) / "carousel" / f"{safe}_{date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": W, "height": H})
        for i, spec in enumerate(slide_specs, 1):
            html = _render_spec(spec, series)
            if not html:
                print(f"[carousel] ✗ slide {i} ({spec.get('type')}) skipped — no content")
                continue
            page.set_content(html, wait_until="networkidle")
            fname = f"{i:02d}_{spec.get('type', 'slide')}.png"
            out   = str(out_dir / fname)
            page.screenshot(path=out)
            paths.append(out)
            print(f"[carousel] ✓ {fname}")
        browser.close()

    return paths
