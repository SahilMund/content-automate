import argparse
import os
import random
import re

from dotenv import load_dotenv

load_dotenv()

from config import OUTPUTS_DIR, TOPICS
from graph.graph import app
from graph.state import AgentState


def _pick_topic() -> str:
    return random.choice(TOPICS)


def _extract_section(brief: str, section: str) -> str:
    m = re.search(rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)", brief, re.DOTALL)
    return m.group(1).strip() if m else "(section not found)"


def _print_divider(label: str = "", char: str = "─", width: int = 54):
    if label:
        print(f"\n{char*3} {label} {char*(width - len(label) - 5)}")
    else:
        print(char * width)


def main():
    parser = argparse.ArgumentParser(
        description="Run the content research + analysis pipeline."
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help='Topic to research, e.g. --topic "FastAPI". Defaults to a random topic.',
    )
    args = parser.parse_args()

    topic = args.topic or _pick_topic()

    print("\n" + "=" * 54)
    print("  content-auto")
    print(f"  topic : {topic}")
    print("=" * 54 + "\n")

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

    result = app.invoke(initial)

    if result.get("error"):
        print(f"\n[ERROR] {result['error']}")
        return

    brief = result["content_brief"]
    retries = result["retry_count"] - 1  # analysis always increments once on a clean run
    safe_topic = topic.lower().replace("/", "-").replace(" ", "_")

    print("\n" + "=" * 54)
    print(f"  quality score : {result['quality_score']}/10")
    print(f"  retries used  : {retries}/{2}")
    print("=" * 54)

    _print_divider("FILES SAVED")
    for f in sorted(os.listdir(OUTPUTS_DIR)):
        if f.endswith(".md") and safe_topic in f:
            print(f"  outputs/{f}")
    img_dir = os.path.join(OUTPUTS_DIR, "images")
    if os.path.isdir(img_dir):
        print(f"  outputs/images/  ({len(result['images'])} images)")

    _print_divider("LINKEDIN POST")
    print(_extract_section(brief, "LinkedIn Post"))

    _print_divider("INSTAGRAM CAPTION")
    print(_extract_section(brief, "Instagram Caption"))

    print("\n" + "─" * 54 + "\n")


if __name__ == "__main__":
    main()
