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
        "id": "almost-closed-laptop",
        "hook": "She almost closed the laptop.",
        "fear": "No one is replying to my applications.",
        "reply": "Then stop sending the same application. Show one proof.",
        "action": "One tiny project became a sharper pitch. The next message got a callback.",
        "headline": "ALMOST QUIT",
        "subhead": "One proof changed the reply.",
        "visual": "spotlight",
    },
    {
        "id": "seven-rejections",
        "hook": "Seven rejections. Then one line changed everything.",
        "fear": "Maybe I am just not internship material.",
        "reply": "Your resume says tasks. Make it show outcomes.",
        "action": "The project line became a result. The next recruiter asked for an interview.",
        "headline": "7 REJECTIONS",
        "subhead": "Then one line changed everything.",
        "visual": "document",
    },
    {
        "id": "almost-skipped",
        "hook": "He almost skipped the interview.",
        "fear": "I do not know every skill they listed.",
        "reply": "They are not hiring a checklist. They are hiring a learner.",
        "action": "He walked in with one honest project story and left with a second round.",
        "headline": "ALMOST SKIPPED",
        "subhead": "Showing up changed the story.",
        "visual": "door",
    },
    {
        "id": "empty-portfolio",
        "hook": "The portfolio was empty at 11:58 PM.",
        "fear": "I have nothing impressive to show.",
        "reply": "Start with useful, not impressive.",
        "action": "A simple case study went live before midnight. It became the first link sent.",
        "headline": "11 58 PM",
        "subhead": "Empty became visible.",
        "visual": "laptop",
    },
    {
        "id": "bus-stop-skill",
        "hook": "A bus stop became the classroom.",
        "fear": "I only get ten free minutes a day.",
        "reply": "Ten focused minutes beats another day of waiting.",
        "action": "One concept per commute became one interview answer per week.",
        "headline": "10 MINUTES",
        "subhead": "Small time. Real momentum.",
        "visual": "clock",
    },
    {
        "id": "messy-teamwork",
        "hook": "The messy group project became the best answer.",
        "fear": "Should I hide that the team struggled?",
        "reply": "No. Real work is how you handle the struggle.",
        "action": "The conflict became a story about ownership, clarity, and leadership.",
        "headline": "MESSY PROJECT",
        "subhead": "The struggle became proof.",
        "visual": "conversation",
    },
    {
        "id": "ignored-message",
        "hook": "The message was ignored. The second one was not.",
        "fear": "What if professionals never reply to students?",
        "reply": "Ask one clear question. Make it easy to answer.",
        "action": "The next note was shorter, specific, and got advice by evening.",
        "headline": "IGNORED",
        "subhead": "The second message worked.",
        "visual": "message",
    },
    {
        "id": "missed-deadline",
        "hook": "One deadline was missed. The career was not.",
        "fear": "I lost the only good opening.",
        "reply": "No. You lost one date, not your direction.",
        "action": "A fresh list went out that night. By morning, three better-fit roles appeared.",
        "headline": "MISSED IT",
        "subhead": "One date is not the end.",
        "visual": "path",
    },
    {
        "id": "ordinary-answer",
        "hook": "The answer sounded boring until this changed.",
        "fear": "My project sounds like everyone else's.",
        "reply": "Tell the problem, your decision, and the result.",
        "action": "The same project became a story that sounded job-ready.",
        "headline": "BORING ANSWER",
        "subhead": "Same project. Better story.",
        "visual": "interview",
    },
    {
        "id": "one-tab-open",
        "hook": "One browser tab stayed open for three weeks.",
        "fear": "I keep saving internships but never applying.",
        "reply": "Saved is not submitted. Pick one and move.",
        "action": "The application took 18 minutes. The confidence lasted all week.",
        "headline": "STILL SAVED",
        "subhead": "Saved is not submitted.",
        "visual": "rocket",
    },
]


@dataclass(frozen=True)
class Story:
    story_id: str
    text: str
    hook: str
    headline: str
    subhead: str
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
        f"{scenario['hook']}\n\n"
        f"{name}: \"{scenario['fear']}\"\n"
        f"{mentor}: \"{scenario['reply']}\"\n"
        f"{scenario['action']}\n\n"
        f"Stop waiting to feel ready. Start here: {SIGNUP_URL}"
    )
    count = word_count(story_text)
    if count > MAX_POST_WORDS:
        raise ValueError(f"Generated story exceeded {MAX_POST_WORDS} words: {count}")
    unique_id = f"{scenario['id']}-{story_hash(story_text)[:12]}"
    return Story(
        story_id=unique_id,
        text=story_text,
        hook=scenario["hook"],
        headline=scenario["headline"],
        subhead=scenario["subhead"],
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


def text_width(text: str, *, scale: int) -> int:
    return sum((4 if char == " " else 6) * scale for char in text.upper())


def centered_text(
    canvas: PngCanvas,
    text: str,
    y: int,
    *,
    scale: int,
    color: tuple[int, int, int],
) -> None:
    width = text_width(text, scale=scale)
    draw_text(canvas, text, max(0, (canvas.width - width) // 2), y, scale=scale, color=color)


def centered_text_fit(
    canvas: PngCanvas,
    text: str,
    y: int,
    *,
    max_scale: int,
    min_scale: int,
    max_width: int,
    color: tuple[int, int, int],
) -> int:
    scale = max_scale
    while scale > min_scale and text_width(text, scale=scale) > max_width:
        scale -= 1
    centered_text(canvas, text, y, scale=scale, color=color)
    return scale


def wrap_display_text(text: str, *, max_chars: int) -> list[str]:
    words = re.sub(r"[^a-zA-Z0-9 ]+", " ", text.upper()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_visual(canvas: PngCanvas, visual: str) -> None:
    blue = (37, 99, 235)
    cyan = (56, 189, 248)
    navy = (15, 23, 42)
    green = (34, 197, 94)
    orange = (249, 115, 22)
    white = (255, 255, 255)

    if visual == "spotlight":
        canvas.line(600, 395, 445, 760, (96, 165, 250), 18)
        canvas.line(600, 395, 755, 760, (96, 165, 250), 18)
        canvas.circle(600, 500, 58, orange)
        canvas.rect(535, 560, 130, 180, orange)
        canvas.rect(350, 790, 500, 38, navy)
        canvas.circle(600, 390, 36, white)
    elif visual == "door":
        canvas.rect(420, 390, 360, 470, navy)
        canvas.rect(465, 440, 270, 420, (30, 64, 175))
        canvas.circle(700, 650, 16, orange)
        canvas.rect(735, 470, 35, 390, (125, 211, 252))
        canvas.line(760, 665, 900, 665, green, 12)
        canvas.line(900, 665, 855, 625, green, 12)
        canvas.line(900, 665, 855, 705, green, 12)
    elif visual == "clock":
        canvas.circle(600, 610, 210, white)
        canvas.circle(600, 610, 190, navy)
        canvas.circle(600, 610, 160, white)
        canvas.line(600, 610, 600, 500, orange, 10)
        canvas.line(600, 610, 705, 650, blue, 10)
        for index in range(6):
            canvas.circle(460 + index * 56, 820 - abs(index - 3) * 20, 18, green)
    elif visual == "message":
        canvas.rect(300, 455, 440, 190, white)
        canvas.rect(300, 455, 440, 25, blue)
        canvas.line(300, 645, 520, 740, blue, 8)
        canvas.line(740, 645, 520, 740, blue, 8)
        canvas.rect(475, 540, 260, 155, orange)
        canvas.rect(515, 585, 170, 14, white)
        canvas.rect(515, 625, 125, 14, white)
    elif visual == "rocket":
        canvas.line(470, 820, 720, 455, white, 55)
        canvas.line(470, 820, 720, 455, blue, 28)
        canvas.circle(720, 455, 46, orange)
        canvas.line(495, 815, 390, 900, orange, 18)
        canvas.line(530, 835, 470, 955, green, 18)
        canvas.line(560, 805, 600, 920, orange, 18)
    elif visual == "laptop":
        canvas.rect(355, 430, 490, 255, navy)
        canvas.rect(385, 460, 430, 195, white)
        canvas.rect(300, 700, 600, 55, blue)
        canvas.line(515, 615, 600, 525, green, 10)
        canvas.line(600, 525, 685, 595, green, 10)
        canvas.line(600, 525, 600, 645, green, 10)
    elif visual == "interview":
        canvas.circle(470, 505, 70, blue)
        canvas.rect(395, 585, 150, 135, blue)
        canvas.circle(730, 505, 70, orange)
        canvas.rect(655, 585, 150, 135, orange)
        canvas.rect(405, 780, 390, 45, navy)
        canvas.line(545, 585, 650, 585, green, 8)
    elif visual == "document":
        canvas.rect(420, 385, 360, 470, white)
        canvas.rect(420, 385, 360, 30, blue)
        for index in range(5):
            canvas.rect(480, 485 + index * 60, 240, 18, navy)
        canvas.line(500, 765, 570, 815, green, 12)
        canvas.line(570, 815, 730, 655, green, 12)
    elif visual == "conversation":
        canvas.rect(300, 460, 390, 155, blue)
        canvas.rect(510, 650, 390, 155, orange)
        canvas.rect(365, 520, 250, 16, white)
        canvas.rect(365, 560, 190, 16, white)
        canvas.rect(575, 710, 250, 16, white)
        canvas.rect(575, 750, 190, 16, white)
    elif visual == "path":
        canvas.line(300, 835, 900, 415, blue, 18)
        canvas.line(900, 415, 830, 420, blue, 18)
        canvas.line(900, 415, 870, 485, blue, 18)
        for index in range(4):
            canvas.circle(375 + index * 130, 765 - index * 92, 24, orange)
    else:
        canvas.line(330, 780, 830, 420, green, 18)
        canvas.line(830, 420, 760, 430, green, 18)
        canvas.line(830, 420, 805, 490, green, 18)
        canvas.rect(350, 805, 120, 120, blue)
        canvas.rect(520, 680, 120, 245, cyan)
        canvas.rect(690, 560, 120, 365, orange)


def create_story_image(story: Story, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{dt.date.today().isoformat()}-{sanitize_filename(story.story_id)}.png"

    canvas = PngCanvas(1200, 1200, (15, 23, 42))
    for y in range(canvas.height):
        ratio = y / canvas.height
        color = (
            int(15 + ratio * 15),
            int(23 + ratio * 41),
            int(42 + ratio * 133),
        )
        canvas.rect(0, y, canvas.width, 1, color)

    canvas.rect(70, 70, 1060, 1060, (8, 13, 30))
    canvas.rect(92, 92, 1016, 1016, (248, 250, 252))
    canvas.rect(92, 92, 1016, 180, (15, 23, 42))
    canvas.rect(92, 272, 1016, 14, (249, 115, 22))
    canvas.circle(1025, 350, 58, (37, 99, 235))
    canvas.circle(180, 1000, 95, (34, 197, 94))
    canvas.rect(150, 305, 900, 3, (203, 213, 225))

    headline_lines = wrap_display_text(story.headline, max_chars=13)
    headline_start = 122 if len(headline_lines) == 1 else 112
    for index, line in enumerate(headline_lines[:2]):
        centered_text_fit(
            canvas,
            line,
            headline_start + index * 72,
            max_scale=10,
            min_scale=6,
            max_width=760,
            color=(255, 255, 255),
        )

    draw_visual(canvas, story.visual)

    subhead_lines = wrap_display_text(story.subhead, max_chars=24)
    for index, line in enumerate(subhead_lines[:2]):
        centered_text_fit(
            canvas,
            line,
            850 + index * 54,
            max_scale=7,
            min_scale=5,
            max_width=870,
            color=(15, 23, 42),
        )

    canvas.rect(260, 965, 680, 72, (249, 115, 22))
    centered_text(canvas, "START HERE", 985, scale=8, color=(255, 255, 255))
    centered_text_fit(
        canvas,
        "STUDENT.WORLDOFINTERNS.COM",
        1065,
        max_scale=6,
        min_scale=4,
        max_width=900,
        color=(15, 23, 42),
    )

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
