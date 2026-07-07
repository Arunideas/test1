#!/usr/bin/env python3
"""Create and post a daily student motivation story to LinkedIn.

The agent creates a short conversation-style story, tracks every used story in
a JSON history file, generates a related PNG image card, and can post both to
LinkedIn through the existing LinkedIn posting agent.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import struct
import sys
import textwrap
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkedin_company_page_agent import LinkedInCompanyPageAgent, LinkedInPostError


SIGNUP_URL = "https://student.worldofinterns.com"
DEFAULT_HISTORY_PATH = Path("daily_story_history.json")
DEFAULT_OUTPUT_DIR = Path("daily_story_output")
MAX_POST_WORDS = 100

NAMES = [
    "Asha",
    "Dev",
    "Meera",
    "Ravi",
    "Nisha",
    "Ibrahim",
    "Kavya",
    "Arjun",
    "Sara",
    "Neel",
]

MENTORS = ["Mentor", "Senior", "Coach", "Friend", "Alumni"]

SCENARIOS = [
    {
        "id": "first-interview",
        "place": "before her first interview",
        "fear": "I only have class projects. Is that enough?",
        "reply": "Show what you built and what you learned. Employers notice action.",
        "action": "She practiced, applied, and booked her first internship call.",
        "headline": "FIRST INTERVIEW",
        "visual": "interview",
    },
    {
        "id": "late-night-portfolio",
        "place": "while updating his portfolio at midnight",
        "fear": "Everyone else looks ahead of me.",
        "reply": "Your next proof matters more than yesterday's doubt.",
        "action": "He uploaded one project and sent three focused applications.",
        "headline": "BUILD PROOF",
        "visual": "laptop",
    },
    {
        "id": "resume-feedback",
        "place": "after getting resume feedback",
        "fear": "My resume feels too small.",
        "reply": "Small becomes strong when every line shows impact.",
        "action": "She rewrote her projects with outcomes and applied the same day.",
        "headline": "RESUME READY",
        "visual": "document",
    },
    {
        "id": "missed-deadline",
        "place": "after missing a deadline",
        "fear": "I think I lost my chance.",
        "reply": "One missed date is not a closed career. Find the next door.",
        "action": "He tracked new openings and submitted before breakfast.",
        "headline": "NEXT DOOR",
        "visual": "path",
    },
    {
        "id": "commute-learning",
        "place": "on the bus to college",
        "fear": "I do not have extra time to prepare.",
        "reply": "Use ten focused minutes daily. Momentum compounds.",
        "action": "She learned one skill on each commute and built a habit.",
        "headline": "10 MINUTES",
        "visual": "path",
    },
    {
        "id": "group-project",
        "place": "after a tough group project",
        "fear": "Teamwork was messy. Should I mention it?",
        "reply": "Yes. Real work is coordination, not perfection.",
        "action": "He turned the challenge into a strong interview story.",
        "headline": "REAL WORK",
        "visual": "conversation",
    },
    {
        "id": "first-rejection",
        "place": "after her first rejection email",
        "fear": "Maybe I am not ready.",
        "reply": "Rejection is data. Improve one thing and try again.",
        "action": "She fixed her pitch and applied to two better-fit roles.",
        "headline": "TRY AGAIN",
        "visual": "arrow",
    },
    {
        "id": "skill-gap",
        "place": "while reading an internship description",
        "fear": "I do not know every skill listed.",
        "reply": "No one starts complete. Match the core and learn fast.",
        "action": "He chose one gap, practiced it, and applied with confidence.",
        "headline": "LEARN FAST",
        "visual": "laptop",
    },
    {
        "id": "mock-interview",
        "place": "during a mock interview",
        "fear": "My answers sound ordinary.",
        "reply": "Add the problem, your action, and the result.",
        "action": "She reframed one project and finally sounded job-ready.",
        "headline": "JOB READY",
        "visual": "interview",
    },
    {
        "id": "first-network-message",
        "place": "before sending a networking message",
        "fear": "What if they ignore me?",
        "reply": "A clear ask is better than silent waiting.",
        "action": "He sent a polite note and got advice by evening.",
        "headline": "ASK CLEARLY",
        "visual": "conversation",
    },
]


@dataclass(frozen=True)
class Story:
    story_id: str
    text: str
    headline: str
    visual: str
    word_count: int


class PngCanvas:
    """Tiny dependency-free RGB PNG canvas for simple social cards."""

    def __init__(self, width: int, height: int, background: tuple[int, int, int]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            index = (y * self.width + x) * 3
            self.pixels[index : index + 3] = bytes(color)

    def rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
    ) -> None:
        for yy in range(max(0, y), min(self.height, y + height)):
            row_start = (yy * self.width + max(0, x)) * 3
            row_end = (yy * self.width + min(self.width, x + width)) * 3
            self.pixels[row_start:row_end] = bytes(color) * max(
                0, min(self.width, x + width) - max(0, x)
            )

    def circle(self, cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        radius_sq = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius_sq:
                    self.set_pixel(x, y, color)

    def line(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: tuple[int, int, int],
        thickness: int = 4,
    ) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        for step in range(steps + 1):
            t = step / steps
            x = round(x1 + (x2 - x1) * t)
            y = round(y1 + (y2 - y1) * t)
            self.circle(x, y, thickness, color)

    def save(self, path: Path) -> None:
        raw = bytearray()
        for y in range(self.height):
            raw.append(0)
            start = y * self.width * 3
            raw.extend(self.pixels[start : start + self.width * 3])

        def chunk(kind: bytes, data: bytes) -> bytes:
            checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

        png = b"\x89PNG\r\n\x1a\n"
        png += chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0),
        )
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        png += chunk(b"IEND", b"")
        path.write_bytes(png)


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01111", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "11110"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "/": ["00001", "00010", "00010", "00100", "01000", "01000", "10000"],
}


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def story_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"used_hashes": [], "posts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("used_hashes", [])
    data.setdefault("posts", [])
    return data


def save_history(path: Path, history: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_story(rng: random.Random, scenario: dict[str, str]) -> Story:
    name = rng.choice(NAMES)
    mentor = rng.choice(MENTORS)
    story_text = (
        f"{name}, {scenario['place']}:\n"
        f"{name}: \"{scenario['fear']}\"\n"
        f"{mentor}: \"{scenario['reply']}\"\n"
        f"{scenario['action']}\n\n"
        f"Your next opportunity can start here: {SIGNUP_URL}"
    )
    count = word_count(story_text)
    if count > MAX_POST_WORDS:
        raise ValueError(f"Generated story exceeded {MAX_POST_WORDS} words: {count}")
    unique_id = f"{scenario['id']}-{story_hash(story_text)[:12]}"
    return Story(
        story_id=unique_id,
        text=story_text,
        headline=scenario["headline"],
        visual=scenario["visual"],
        word_count=count,
    )


def choose_unused_story(history: dict[str, Any], *, seed: int | None = None) -> Story:
    used_hashes = set(history.get("used_hashes", []))
    rng = random.Random(seed)
    for _ in range(300):
        story = build_story(rng, rng.choice(SCENARIOS))
        if story_hash(story.text) not in used_hashes:
            return story
    raise RuntimeError("Could not create a new unused story after 300 attempts.")


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "story"


def draw_text(
    canvas: PngCanvas,
    text: str,
    x: int,
    y: int,
    *,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    cursor_x = x
    for char in text.upper():
        if char == " ":
            cursor_x += scale * 4
            continue
        glyph = FONT.get(char)
        if not glyph:
            cursor_x += scale * 4
            continue
        for row_index, row in enumerate(glyph):
            for column_index, bit in enumerate(row):
                if bit == "1":
                    canvas.rect(
                        cursor_x + column_index * scale,
                        y + row_index * scale,
                        scale,
                        scale,
                        color,
                    )
        cursor_x += scale * 6


def centered_text(
    canvas: PngCanvas,
    text: str,
    y: int,
    *,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    width = sum((4 if char == " " else 6) * scale for char in text.upper())
    draw_text(canvas, text, max(0, (canvas.width - width) // 2), y, scale=scale, color=color)


def draw_visual(canvas: PngCanvas, visual: str) -> None:
    blue = (37, 99, 235)
    cyan = (56, 189, 248)
    navy = (15, 23, 42)
    green = (34, 197, 94)
    orange = (249, 115, 22)
    white = (255, 255, 255)

    if visual == "laptop":
        canvas.rect(355, 360, 490, 290, navy)
        canvas.rect(385, 390, 430, 230, white)
        canvas.rect(300, 660, 600, 55, blue)
        canvas.line(515, 575, 600, 485, green, 10)
        canvas.line(600, 485, 685, 555, green, 10)
        canvas.line(600, 485, 600, 605, green, 10)
    elif visual == "interview":
        canvas.circle(470, 455, 70, blue)
        canvas.rect(395, 535, 150, 135, blue)
        canvas.circle(730, 455, 70, orange)
        canvas.rect(655, 535, 150, 135, orange)
        canvas.rect(405, 730, 390, 45, navy)
        canvas.line(545, 535, 650, 535, green, 8)
    elif visual == "document":
        canvas.rect(420, 330, 360, 470, white)
        canvas.rect(420, 330, 360, 30, blue)
        for index in range(5):
            canvas.rect(480, 430 + index * 60, 240, 18, navy)
        canvas.line(500, 710, 570, 760, green, 12)
        canvas.line(570, 760, 730, 600, green, 12)
    elif visual == "conversation":
        canvas.rect(330, 380, 360, 155, blue)
        canvas.rect(510, 575, 360, 155, orange)
        canvas.rect(390, 440, 240, 16, white)
        canvas.rect(390, 480, 190, 16, white)
        canvas.rect(570, 635, 240, 16, white)
        canvas.rect(570, 675, 190, 16, white)
    elif visual == "path":
        canvas.line(300, 780, 900, 360, blue, 18)
        canvas.line(900, 360, 830, 365, blue, 18)
        canvas.line(900, 360, 870, 430, blue, 18)
        for index in range(4):
            canvas.circle(375 + index * 130, 710 - index * 92, 24, orange)
    else:
        canvas.line(330, 720, 830, 360, green, 18)
        canvas.line(830, 360, 760, 370, green, 18)
        canvas.line(830, 360, 805, 430, green, 18)
        canvas.rect(350, 745, 120, 120, blue)
        canvas.rect(520, 620, 120, 245, cyan)
        canvas.rect(690, 500, 120, 365, orange)


def create_story_image(story: Story, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{dt.date.today().isoformat()}-{sanitize_filename(story.story_id)}.png"

    canvas = PngCanvas(1200, 1200, (239, 246, 255))
    for y in range(canvas.height):
        ratio = y / canvas.height
        color = (
            int(239 - ratio * 24),
            int(246 - ratio * 30),
            int(255 - ratio * 10),
        )
        canvas.rect(0, y, canvas.width, 1, color)

    canvas.rect(80, 80, 1040, 1040, (255, 255, 255))
    canvas.rect(80, 80, 1040, 16, (37, 99, 235))
    canvas.circle(180, 185, 42, (34, 197, 94))
    canvas.circle(1010, 1010, 70, (191, 219, 254))

    centered_text(canvas, story.headline, 165, scale=18, color=(15, 23, 42))
    draw_visual(canvas, story.visual)
    centered_text(canvas, "ONE STEP TODAY", 875, scale=14, color=(37, 99, 235))
    centered_text(canvas, "STUDENT.WORLDOFINTERNS.COM", 1000, scale=8, color=(15, 23, 42))

    canvas.save(image_path)
    return image_path


def record_story(
    history: dict[str, Any],
    story: Story,
    *,
    image_path: Path,
    post_result: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    content_hash = story_hash(story.text)
    entry = {
        "story_id": story.story_id,
        "content_hash": content_hash,
        "word_count": story.word_count,
        "text": story.text,
        "image_path": str(image_path),
        "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dry_run": dry_run,
        "post_response": post_result,
    }
    history.setdefault("posts", []).append(entry)
    if not dry_run:
        history.setdefault("used_hashes", []).append(content_hash)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and optionally post a unique daily student story.",
    )
    parser.add_argument(
        "--history-path",
        default=os.getenv("DAILY_STORY_HISTORY_PATH", str(DEFAULT_HISTORY_PATH)),
        help="JSON file used to track posted story hashes.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("DAILY_STORY_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory for generated story images.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for repeatable dry-run testing.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Publish to LinkedIn. Omit for dry-run generation only.",
    )
    parser.add_argument(
        "--record-dry-run",
        action="store_true",
        help="Write dry-run output to history without marking the story as used.",
    )
    parser.add_argument(
        "--post-as",
        choices=("member", "organization"),
        default=os.getenv("LINKEDIN_POST_AS", "member"),
        help="LinkedIn author type. Defaults to member for personal posting.",
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("LINKEDIN_ACCESS_TOKEN"),
        help="LinkedIn access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--member-id",
        default=os.getenv("LINKEDIN_MEMBER_ID"),
        help="LinkedIn member id for personal posts.",
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("LINKEDIN_ORGANIZATION_ID"),
        help="LinkedIn organization id for company page posts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    history_path = Path(args.history_path)
    output_dir = Path(args.output_dir)

    try:
        history = load_history(history_path)
        story = choose_unused_story(history, seed=args.seed)
        image_path = create_story_image(story, output_dir)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    post_result: dict[str, Any] | None = None
    if args.post:
        agent = LinkedInCompanyPageAgent(
            organization_urn=(
                f"urn:li:organization:{args.organization_id}"
                if args.organization_id
                else "urn:li:organization:YOUR_ORGANIZATION_ID"
            ),
            member_urn=f"urn:li:person:{args.member_id}" if args.member_id else None,
            access_token=args.access_token,
        )
        try:
            post_result = agent.post_image(
                story.text,
                image_path=str(image_path),
                dry_run=False,
                post_as=args.post_as,
                image_title=story.headline.title(),
                image_description="Student motivation story from World of Interns",
            )
        except (LinkedInPostError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    if args.post or args.record_dry_run:
        record_story(
            history,
            story,
            image_path=image_path,
            post_result=post_result,
            dry_run=not args.post,
        )
        try:
            save_history(history_path, history)
        except OSError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    response = {
        "dry_run": not args.post,
        "story_id": story.story_id,
        "word_count": story.word_count,
        "story": story.text,
        "image_path": str(image_path),
        "history_path": str(history_path),
        "recorded": args.post or args.record_dry_run,
        "post_response": post_result,
    }
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
