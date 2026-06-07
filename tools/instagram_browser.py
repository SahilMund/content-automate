"""
Post a photo to Instagram using Playwright + saved Chrome cookies.
Runs fully headless — no visible window, safe to call from the Telegram bot.

One-time setup: python auth_instagram_cookies.py
Re-run that script if Instagram ever logs you out (~90 days).
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

COOKIES_FILE    = os.path.join(os.path.dirname(__file__), "..", "ig_cookies.json")
EXPECTED_USER   = os.getenv("INSTAGRAM_USERNAME", "").lower().strip()


def post_to_instagram_browser(caption: str, image_path: str) -> str:
    from playwright.sync_api import TimeoutError as PwTimeout
    from playwright.sync_api import sync_playwright

    image_path = str(Path(image_path).resolve())
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    cookies_path = os.path.abspath(COOKIES_FILE)
    if not os.path.exists(cookies_path):
        raise RuntimeError(
            "ig_cookies.json not found. Run: python auth_instagram_cookies.py"
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            storage_state=cookies_path,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── Step 1: open Instagram ─────────────────────────────
        page.goto("https://www.instagram.com/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Verify we're logged in (not on login page)
        if "accounts/login" in page.url:
            context.close()
            browser.close()
            raise RuntimeError(
                "Instagram session expired. Re-run: python auth_instagram_cookies.py"
            )

        # ── Verify correct account ─────────────────────────────
        import re as _re
        hrefs = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href]');
            return [...links].map(a => a.getAttribute('href'));
        }""")
        # Profile href looks like /username/ — pick the one matching EXPECTED_USER
        profile_hrefs = [h for h in hrefs if h and _re.match(r'^/[a-zA-Z0-9._]+/$', h)]
        logged_in_as = ""
        if EXPECTED_USER:
            match = next((h.strip("/").lower() for h in profile_hrefs if h.strip("/").lower() == EXPECTED_USER), None)
            if match:
                logged_in_as = match
            else:
                # Fallback: pick the most frequent profile href
                from collections import Counter
                counts = Counter(h.strip("/").lower() for h in profile_hrefs)
                logged_in_as = counts.most_common(1)[0][0] if counts else ""

        if EXPECTED_USER and logged_in_as != EXPECTED_USER:
            context.close()
            browser.close()
            raise RuntimeError(
                f"Wrong Instagram account! Expected @{EXPECTED_USER} "
                f"but logged-in account is @{logged_in_as or 'unknown'}. "
                f"Re-run: python auth_instagram_cookies.py"
            )
        print(f"[instagram] Verified account: @{logged_in_as or EXPECTED_USER}")

        # Dismiss "Turn on Notifications" popup if it appears
        not_now = page.get_by_role("button", name="Not Now")
        if not_now.is_visible(timeout=3000):
            not_now.click()
            time.sleep(1)

        # ── Step 2: click Create → Post ────────────────────────
        create_btn = page.locator("a:has(svg[aria-label='New post'])").first
        if not create_btn.is_visible(timeout=5000):
            create_btn = page.locator("svg[aria-label='New post']").first
        create_btn.click(timeout=10000, force=True)
        time.sleep(1)
        # A sub-menu appears with "Post" and "AI" options — click the Post item
        page.get_by_role("link", name="Post Post").click(timeout=5000)
        time.sleep(1)

        # ── Step 3: upload image ───────────────────────────────
        # Wait for file input (hidden) then set file directly
        page.wait_for_selector("input[type='file']", state="attached", timeout=10000)
        page.locator("input[type='file']").set_input_files(image_path)
        time.sleep(2)

        # ── Step 4: Crop → Next ────────────────────────────────
        page.get_by_role("button", name="Next").click(timeout=10000)
        time.sleep(1)

        # ── Step 5: Filters → Next ────────────────────────────
        page.get_by_role("button", name="Next").click(timeout=10000)
        time.sleep(1)

        # ── Step 6: Caption ────────────────────────────────────
        caption_box = page.locator("div[aria-label='Write a caption...']")
        caption_box.wait_for(timeout=10000)
        caption_box.click()
        caption_box.fill(caption)
        time.sleep(1)

        # ── Step 7: Share ──────────────────────────────────────
        page.get_by_role("button", name="Share", exact=True).click(timeout=15000)

        try:
            page.wait_for_selector("text=Your post has been shared", timeout=30000)
        except PwTimeout:
            time.sleep(5)

        context.close()
        browser.close()

    return "https://www.instagram.com/"


def post_reel_to_instagram_browser(caption: str, video_path: str) -> str:
    """
    Upload an MP4 as an Instagram Reel via headless Playwright.
    Uses the standard "Post" flow — Instagram automatically converts
    video uploads to Reels (shows "Video posts are now shared as reels" popup).
    """
    from playwright.sync_api import TimeoutError as PwTimeout
    from playwright.sync_api import sync_playwright

    video_path = str(Path(video_path).resolve())
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cookies_path = os.path.abspath(COOKIES_FILE)
    if not os.path.exists(cookies_path):
        raise RuntimeError(
            "ig_cookies.json not found. Run: python auth_instagram_cookies.py"
        )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            storage_state=cookies_path,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        page.goto("https://www.instagram.com/", wait_until="networkidle", timeout=30000)
        time.sleep(2)

        if "accounts/login" in page.url:
            context.close()
            browser.close()
            raise RuntimeError(
                "Instagram session expired. Re-run: python auth_instagram_cookies.py"
            )

        # ── Account verification ───────────────────────────────
        import re as _re
        hrefs = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href]');
            return [...links].map(a => a.getAttribute('href'));
        }""")
        profile_hrefs = [h for h in hrefs if h and _re.match(r'^/[a-zA-Z0-9._]+/$', h)]
        logged_in_as = ""
        if EXPECTED_USER:
            match = next((h.strip("/").lower() for h in profile_hrefs if h.strip("/").lower() == EXPECTED_USER), None)
            if match:
                logged_in_as = match
            else:
                from collections import Counter
                counts = Counter(h.strip("/").lower() for h in profile_hrefs)
                logged_in_as = counts.most_common(1)[0][0] if counts else ""

        if EXPECTED_USER and logged_in_as != EXPECTED_USER:
            context.close()
            browser.close()
            raise RuntimeError(
                f"Wrong Instagram account! Expected @{EXPECTED_USER} "
                f"but logged-in account is @{logged_in_as or 'unknown'}. "
                f"Re-run: python auth_instagram_cookies.py"
            )
        print(f"[instagram-reel] Verified account: @{logged_in_as or EXPECTED_USER}")

        not_now = page.get_by_role("button", name="Not Now")
        if not_now.is_visible(timeout=3000):
            not_now.click()
            time.sleep(1)

        # ── Click New post → Post (same as photo — Instagram auto-converts video to Reel)
        create_btn = page.locator("a:has(svg[aria-label='New post'])").first
        if not create_btn.is_visible(timeout=5000):
            create_btn = page.locator("svg[aria-label='New post']").first
        create_btn.click(timeout=10000, force=True)
        time.sleep(1)
        page.get_by_role("link", name="Post Post").click(timeout=5000)
        time.sleep(1)

        # ── Upload video ───────────────────────────────────────
        page.wait_for_selector("input[type='file']", state="attached", timeout=10000)
        page.locator("input[type='file']").set_input_files(video_path)
        time.sleep(4)

        # ── Dismiss "Video posts are now shared as reels" popup ─
        ok_btn = page.get_by_role("button", name="OK")
        if ok_btn.is_visible(timeout=5000):
            ok_btn.click()
            time.sleep(2)

        # ── Next (crop/trim) ───────────────────────────────────
        page.get_by_role("button", name="Next").click(timeout=10000)
        time.sleep(2)

        # ── Next (effects/filters → caption screen) ───────────
        page.get_by_role("button", name="Next").click(timeout=10000)
        time.sleep(2)

        # ── Caption ────────────────────────────────────────────
        caption_box = page.locator("div[aria-label='Write a caption...']")
        caption_box.wait_for(timeout=10000)
        caption_box.click()
        caption_box.fill(caption)
        time.sleep(1)

        # ── Share ──────────────────────────────────────────────
        page.get_by_role("button", name="Share", exact=True).click(timeout=15000)
        try:
            page.wait_for_selector("text=Your reel has been shared", timeout=60000)
        except PwTimeout:
            time.sleep(10)

        context.close()
        browser.close()

    return "https://www.instagram.com/"
