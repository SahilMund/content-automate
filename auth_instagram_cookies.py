"""
One-time script: extracts Instagram cookies from Chrome Profile 1
and saves them as ig_cookies.json (Playwright storage state format).

Run once: python auth_instagram_cookies.py
Re-run if Instagram logs you out (cookies expire after ~90 days).
"""
import json
import os

CHROME_PROFILE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Profile 1"
)
OUTPUT = os.path.join(os.path.dirname(__file__), "ig_cookies.json")


def extract():
    import browser_cookie3

    db_path = os.path.join(CHROME_PROFILE, "Cookies")
    cookies = list(browser_cookie3.chrome(
        cookie_file=db_path, domain_name="instagram.com"
    ))

    if not any(c.name == "sessionid" for c in cookies):
        print("❌ No Instagram sessionid found in Chrome Profile 1.")
        print("   Make sure you're logged into instagram.com in Chrome Profile 1.")
        return False

    # Convert to Playwright storage state format
    storage_state = {
        "cookies": [
            {
                "name":     c.name,
                "value":    c.value,
                "domain":   c.domain if c.domain.startswith(".") else f".{c.domain}",
                "path":     c.path or "/",
                "expires":  int(c.expires) if c.expires else -1,
                "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")),
                "secure":   bool(c.secure),
                "sameSite": "Lax",
            }
            for c in cookies
        ],
        "origins": [],
    }

    with open(OUTPUT, "w") as f:
        json.dump(storage_state, f, indent=2)

    print(f"✅ Saved {len(storage_state['cookies'])} cookies → {OUTPUT}")
    print("   Instagram posting will now run fully headless — no Chrome window.")
    return True


if __name__ == "__main__":
    extract()
