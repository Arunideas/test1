#!/usr/bin/env python3
"""Create and post a daily student motivation story to LinkedIn.

The agent creates a short conversation-style story, tracks every used story in
a JSON history file, generates a related PNG image card, and can post both to
LinkedIn through the existing LinkedIn posting agent.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import random
import re
import struct
import sys
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from linkedin_company_page_agent import LinkedInCompanyPageAgent, LinkedInPostError


SIGNUP_URL = "https://student.worldofinterns.com"
DEFAULT_HISTORY_PATH = Path("daily_story_history.json")
DEFAULT_OUTPUT_DIR = Path("daily_story_output")
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"
DEFAULT_OPENAI_IMAGE_SIZE = "1024x1024"
MIN_POST_WORDS = 200
MAX_POST_WORDS = 500

DEFAULT_METRICS = {
    "python_assessment_students": "12,487",
    "python_function_success_rate": "18%",
    "mechanical_resume_year": "2026",
    "mechanical_resume_missing_skills": (
        "CAD documentation, Excel reporting, GD&T basics, manufacturing process "
        "knowledge, and project cost estimation"
    ),
    "github_interview_multiplier": "2.8x",
    "average_employability_score": "61/100",
    "top_college_score": "84/100",
    "bottom_college_score": "42/100",
    "data_analyst_resume_gap": "SQL portfolio projects",
    "startup_shortlist_rate": "31%",
    "role_ranking_top_role": "Data Analyst Intern",
}

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

CONTENT_ANGLES = [
    {
        "id": "assessment-python-function-errors",
        "content_type": "Assessment Scores",
        "hook": "{python_assessment_students} students took our Python assessment this month. Only {python_function_success_rate} could write a function without errors.",
        "headline": "PYTHON GAP",
        "subhead": "Syntax is not the skill. Problem solving is.",
        "visual": "laptop",
        "setup": (
            "{python_assessment_students} students attempted a Python readiness "
            "assessment this month, and only {python_function_success_rate} could "
            "write a clean function without errors. That gap matters because most "
            "internship tasks start with small, reliable functions."
        ),
        "sections": [
            "The issue is rarely motivation. Students watch tutorials, but they do not practice enough blank-screen coding.",
            "The most common gap is function structure: inputs, return values, edge cases, and readable naming.",
            "The employability signal is not 'I know Python.' It is 'I can solve a small problem correctly without hand-holding.'",
        ],
        "action": "Take one basic problem today and write it as a function without copying. Then explain what input it accepts, what output it returns, and where it can fail.",
    },
    {
        "id": "mechanical-resume-skill-gaps",
        "content_type": "Skill Gap Analysis",
        "hook": "Top 5 skills missing from Mechanical Engineering resumes in {mechanical_resume_year}.",
        "headline": "SKILL GAPS",
        "subhead": "Mechanical resumes need proof.",
        "visual": "document",
        "setup": (
            "Mechanical Engineering resumes often list workshops, software names, "
            "and college projects, but the missing skills are usually the signals "
            "that make a recruiter believe the student can contribute on day one."
        ),
        "sections": [
            "The top missing skills are: {mechanical_resume_missing_skills}.",
            "The problem is not that students never touched these areas. The problem is that resumes rarely show applied proof.",
            "A stronger resume connects each skill to a project, drawing, analysis, process improvement, or measurable output.",
        ],
        "action": "Pick one missing skill from the list and attach it to a real project line. Do not write 'knowledge of CAD.' Write what you designed, why it mattered, and what constraint you handled.",
    },
    {
        "id": "github-portfolio-interview-calls",
        "content_type": "Resume Data",
        "hook": "Students with GitHub portfolios received {github_interview_multiplier} more interview calls than those without one.",
        "headline": "PORTFOLIO WINS",
        "subhead": "Proof beats claims.",
        "visual": "message",
        "setup": (
            "A resume can claim skills, but a portfolio lets recruiters inspect "
            "proof. Students with GitHub portfolios received {github_interview_multiplier} "
            "more interview calls than students who listed skills without visible work."
        ),
        "sections": [
            "The portfolio does not need to be huge. Two clean projects with README files can outperform ten unsupported skill keywords.",
            "Recruiters look for structure: what the project solves, how to run it, what tools were used, and what the student learned.",
            "A visible portfolio reduces risk. It tells the company the student can finish, document, and explain work.",
        ],
        "action": "If you have one project sitting on your laptop, upload it, write a simple README, add screenshots, and link it on your resume today.",
    },
    {
        "id": "employability-score-distribution",
        "content_type": "Employability Scores",
        "hook": "The average employability score this cycle is {average_employability_score}. That number explains why applications feel stuck.",
        "headline": "SCORE CHECK",
        "subhead": "Readiness can be measured.",
        "visual": "clock",
        "setup": (
            "Employability becomes easier to improve when students stop treating it "
            "as a vague feeling. The average score this cycle is {average_employability_score}, "
            "which means many students are close, but not yet role-ready."
        ),
        "sections": [
            "Low scores usually come from weak proof: resumes list skills but do not show outcomes.",
            "Medium scores usually have projects, but the role fit is unclear.",
            "High scores combine resume clarity, assessment performance, portfolio proof, and interview readiness.",
        ],
        "action": "Score yourself across resume, skills, projects, profile, and interview answers. Then improve the lowest area first instead of randomly applying everywhere.",
    },
    {
        "id": "college-wise-performance-gap",
        "content_type": "College-wise Performance",
        "hook": "The top college scored {top_college_score}. The lowest scored {bottom_college_score}. The difference was not branding.",
        "headline": "COLLEGE GAP",
        "subhead": "Performance beats perception.",
        "visual": "arrow",
        "setup": (
            "College-wise performance becomes useful when it focuses on student "
            "readiness, not reputation alone. In the latest comparison, the top "
            "college scored {top_college_score}, while the lowest scored {bottom_college_score}."
        ),
        "sections": [
            "The strongest colleges had more students with completed projects, clearer resumes, and better assessment consistency.",
            "The weaker colleges were not missing talent. They were missing visible proof and structured preparation.",
            "A college can improve its employability score when students practice role-specific tasks before placement season begins.",
        ],
        "action": "If you are a college team, track proof weekly: project completion, resume quality, assessment scores, and interview readiness. That is where ranking improvement starts.",
    },
    {
        "id": "role-wise-ranking-data-analyst",
        "content_type": "Role-wise Rankings",
        "hook": "{role_ranking_top_role} is ranking high, but one gap keeps students out: {data_analyst_resume_gap}.",
        "headline": "ROLE RANKING",
        "subhead": "Role fit needs evidence.",
        "visual": "spotlight",
        "setup": (
            "{role_ranking_top_role} is ranking high among student targets, but "
            "the resume gap that keeps appearing is {data_analyst_resume_gap}. "
            "Students want the role, but the proof often does not match the job."
        ),
        "sections": [
            "A role-wise ranking is useful only when it shows the gap between demand and readiness.",
            "For analytics roles, recruiters expect evidence of cleaning data, querying data, visualizing insights, and explaining decisions.",
            "Students who show one complete analytics workflow look more credible than students who list five disconnected tools.",
        ],
        "action": "Choose one target role and build one project that proves the core workflow for that role. Generic preparation creates generic results.",
    },
    {
        "id": "recruiter-secret-eight-seconds",
        "content_type": "Recruiter Secrets",
        "hook": "Why I rejected this resume in 8 seconds.",
        "headline": "8 SECOND REJECT",
        "subhead": "Recruiters scan for proof first.",
        "visual": "spotlight",
        "setup": (
            "A recruiter opens a resume and does not read it like a student does. "
            "They scan for proof, signal, and fit. If those three things are hidden, "
            "the resume feels risky before the candidate gets a chance."
        ),
        "sections": [
            "The first problem: the top half says 'hardworking student' but does not show one specific skill used in a real project.",
            "The second problem: the project line says 'worked on app' instead of explaining the problem, tool, and result.",
            "The fix: replace vague effort with evidence. Example: 'Built a Python dashboard that reduced manual report time by 30%.'",
        ],
        "action": "Open your resume today and underline every line that proves a skill. If a line only says you participated, rewrite it until it shows evidence.",
    },
    {
        "id": "resume-roast-before-after",
        "content_type": "Resume Roast",
        "hook": "Resume roast: this line sounds busy, not employable.",
        "headline": "RESUME ROAST",
        "subhead": "Before and after that gets noticed.",
        "visual": "document",
        "setup": (
            "Most students do not have a weak resume because they lack talent. "
            "They have a weak resume because their strongest work is written like a classroom note."
        ),
        "sections": [
            "Before: 'Completed machine learning project in college.' This tells the recruiter almost nothing.",
            "After: 'Trained a model to predict student drop-off risk using Python, cleaned 2,000 rows, and presented accuracy trade-offs.'",
            "Why it works: the after version shows tool, scale, problem, and communication. That is employability language.",
        ],
        "action": "Pick one project and rewrite it with this formula: built what, using which tool, for what problem, with what result.",
    },
    {
        "id": "interview-mistake-real-scenario",
        "content_type": "Interview Mistakes",
        "hook": "The interview was going well until this answer.",
        "headline": "INTERVIEW TRAP",
        "subhead": "One common answer kills trust.",
        "visual": "interview",
        "setup": (
            "A student is asked, 'Tell me about a project you are proud of.' "
            "The answer starts with confidence, but then becomes a list of features. "
            "That is where many interviews quietly fall apart."
        ),
        "sections": [
            "Mistake: explaining every screen, library, and feature without naming the problem.",
            "Better answer: 'The problem was slow manual tracking. My role was data cleanup and dashboard logic. The result was faster weekly reporting.'",
            "Recruiters are not testing memory. They are testing whether you understand impact, ownership, and trade-offs.",
        ],
        "action": "Prepare one project answer with four parts: problem, your role, hard decision, measurable result.",
    },
    {
        "id": "skill-battle-python-excel",
        "content_type": "Skill Battles",
        "hook": "Python vs Excel: which one gets more internships?",
        "headline": "SKILL BATTLE",
        "subhead": "The winner depends on proof.",
        "visual": "laptop",
        "setup": (
            "Students often ask which skill is more valuable. The honest answer is that companies do not hire tools. "
            "They hire people who can solve problems with tools."
        ),
        "sections": [
            "Excel wins when the role needs reporting, cleanup, dashboards, and business decisions quickly.",
            "Python wins when the role needs automation, analysis at scale, scraping, APIs, or repeatable workflows.",
            "The real winner is the student who can show one before-and-after result: messy data to useful decision.",
        ],
        "action": "Build one mini project twice: solve it in Excel, then automate one part in Python. That comparison becomes interview gold.",
    },
    {
        "id": "student-transformation-profile",
        "content_type": "Student Transformations",
        "hook": "Same student. Same skills. Completely different profile.",
        "headline": "PROFILE UPGRADE",
        "subhead": "Small changes can change perception.",
        "visual": "message",
        "setup": (
            "A student profile can look average even when the student has done meaningful work. "
            "The transformation usually starts by moving from claims to proof."
        ),
        "sections": [
            "Before: headline says 'B.Tech student looking for opportunities.' It sounds passive and common.",
            "After: headline says 'Data analytics student building Excel and Python dashboards for campus problems.' Now there is direction.",
            "Before: projects are hidden. After: one pinned project, one result-driven summary, and one clear skill stack are visible.",
        ],
        "action": "Update your profile today with one proof line, one pinned project, and one sentence about the problem you want to solve.",
    },
    {
        "id": "weekly-employability-challenge",
        "content_type": "Weekly Employability Challenges",
        "hook": "Can you score 80/100 on employability this week?",
        "headline": "80 OUT OF 100",
        "subhead": "A simple weekly readiness challenge.",
        "visual": "clock",
        "setup": (
            "Employability is not a mood. It can be scored through visible signals: proof, clarity, communication, consistency, and role fit."
        ),
        "sections": [
            "20 points: your resume has at least three project lines with tools and outcomes.",
            "20 points: your profile explains what role you want and why you are credible for it.",
            "20 points: you can explain one project in 60 seconds. 20 points: you applied to roles that match your proof. 20 points: you asked for feedback.",
        ],
        "action": "Score yourself honestly. If you are below 80, do not panic. Fix the lowest category first and check again tomorrow.",
    },
    {
        "id": "college-employability-ranking",
        "content_type": "College Rankings",
        "hook": "A college ranking that actually matters: employability score.",
        "headline": "RANK BY PROOF",
        "subhead": "Placements start before final year.",
        "visual": "arrow",
        "setup": (
            "The useful question is not only which college has the biggest name. "
            "The sharper question is which college helps students become visibly employable."
        ),
        "sections": [
            "A strong employability score looks at project proof, internship readiness, interview practice, recruiter access, and student consistency.",
            "A college with average branding but strong student proof can outperform a famous college where students wait passively.",
            "Rankings become useful when they push action: better resumes, better projects, better employer conversations.",
        ],
        "action": "Ask your college community this week: how many students can show a role-ready project today, not just a certificate?",
    },
    {
        "id": "company-expectations-startups",
        "content_type": "Company Expectations",
        "hook": "What startups actually test before hiring interns.",
        "headline": "STARTUP TEST",
        "subhead": "Speed, ownership, and proof matter.",
        "visual": "door",
        "setup": (
            "Startups rarely have time to train someone from zero. They look for students who can learn fast, communicate clearly, and finish useful work."
        ),
        "sections": [
            "They test whether you can understand an unclear problem without waiting for perfect instructions.",
            "They test whether your portfolio shows shipped work, not just course completion.",
            "They test whether you ask better questions, share progress early, and recover when something breaks.",
        ],
        "action": "Before applying to a startup, prepare one example where you took ownership without being pushed. That story can separate you from dozens of applicants.",
    },
]


@dataclass(frozen=True)
class Story:
    story_id: str
    text: str
    content_type: str
    assets: dict[str, str]
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


class SafeMetrics(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_metrics(path: Path | None) -> dict[str, str]:
    metrics = dict(DEFAULT_METRICS)
    if path is None:
        return metrics
    if not path.exists():
        raise FileNotFoundError(f"Metrics file does not exist: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Metrics file must contain a JSON object.")
    for key, value in loaded.items():
        metrics[str(key)] = str(value)
    return metrics


def render_metric_template(value: str, metrics: dict[str, str]) -> str:
    return value.format_map(SafeMetrics(metrics))


def render_content_angle(angle: dict[str, Any], metrics: dict[str, str]) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    for key, value in angle.items():
        if isinstance(value, str):
            rendered[key] = render_metric_template(value, metrics)
        elif isinstance(value, list):
            rendered[key] = [
                render_metric_template(item, metrics) if isinstance(item, str) else item
                for item in value
            ]
        else:
            rendered[key] = value
    return rendered


def build_content_assets(
    rng: random.Random,
    angle: dict[str, Any],
    *,
    student_name: str,
) -> dict[str, str]:
    proof_task = rng.choice(
        [
            "rewrite one resume bullet",
            "record one 60-second project explanation",
            "send one focused networking message",
            "publish one small project proof",
            "apply to one role that matches your evidence",
        ]
    )
    sections = "\n".join(
        f"{index}. {section}" for index, section in enumerate(angle["sections"], start=1)
    )
    topic = f"{angle['content_type']}: {angle['hook']}"
    insight = (
        f"{angle['setup']} For a student like {student_name}, this is not theory. "
        f"It is the difference between being another applicant and becoming a "
        f"candidate with a signal recruiters can remember.\n\n"
        f"Here is the breakdown:\n{sections}"
    )
    story = (
        "What most students miss is that employability is built in public signals. "
        "A certificate helps only when it connects to a project. A project helps "
        "only when it explains a problem. A profile helps only when it tells a "
        "recruiter what to trust. The student who makes proof easy to see wins "
        "attention faster than the student who only says, \"I am passionate.\"\n\n"
        f"Your move today: {angle['action']} If you want a small starting point, "
        f"{proof_task}. Do not wait until your profile feels perfect. Make one "
        "useful improvement, then make the next application with more evidence "
        "than yesterday.\n\n"
        "This is how internships become more than luck: stronger proof, sharper "
        "communication, and consistent action. Save this, try the action, and "
        "check your employability score again tomorrow."
    )
    visual = (
        f"Photorealistic LinkedIn image concept: {angle['headline']} - "
        f"{angle['subhead']}. Show students in a realistic campus or early-career "
        "workspace moment with curiosity, proof, and action visible."
    )
    cta = f"Stop waiting to feel ready. Start here: {SIGNUP_URL}"
    return {
        "topic": topic,
        "insight": insight,
        "story": story,
        "visual": visual,
        "cta": cta,
    }


def format_content_text(assets: dict[str, str]) -> str:
    return (
        f"Topic:\n{assets['topic']}\n\n"
        f"Insight:\n{assets['insight']}\n\n"
        f"Story:\n{assets['story']}\n\n"
        f"CTA:\n{assets['cta']}"
    )


def build_story(
    rng: random.Random,
    angle: dict[str, Any],
    *,
    metrics: dict[str, str],
) -> Story:
    angle = render_content_angle(angle, metrics)
    name = rng.choice(NAMES)
    assets = build_content_assets(rng, angle, student_name=name)
    story_text = format_content_text(assets)
    count = word_count(story_text)
    if not MIN_POST_WORDS <= count <= MAX_POST_WORDS:
        raise ValueError(
            f"Generated story must be between {MIN_POST_WORDS} and "
            f"{MAX_POST_WORDS} words; got {count}."
        )
    unique_id = f"{angle['id']}-{story_hash(story_text)[:12]}"
    return Story(
        story_id=unique_id,
        text=story_text,
        content_type=angle["content_type"],
        assets=assets,
        hook=angle["hook"],
        headline=angle["headline"],
        subhead=angle["subhead"],
        visual=angle["visual"],
        word_count=count,
    )


def choose_unused_story(
    history: dict[str, Any],
    *,
    metrics: dict[str, str],
    seed: int | None = None,
) -> Story:
    used_hashes = set(history.get("used_hashes", []))
    rng = random.Random(seed)
    for _ in range(300):
        story = build_story(rng, rng.choice(CONTENT_ANGLES), metrics=metrics)
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


def build_photographic_image_prompt(story: Story) -> str:
    return (
        "Create a square photorealistic LinkedIn social image for a student "
        "employability content post. "
        "Show diverse college students or early-career young adults in a real "
        "life moment connected to this topic: "
        f"{story.content_type}. "
        f"{story.hook} "
        f"Visual direction: {story.assets['visual']} "
        "The image should feel cinematic, curious, practical, and aspirational, "
        "with natural lighting, realistic faces, modern campus or workspace "
        "environment, shallow depth of field, and a clear focal person. Add "
        "subtle editorial graphic modifications on top, such as a translucent "
        "gradient, small arrow marks, notification-style highlights, or a "
        "spotlight effect. Make it attractive for LinkedIn and motivational "
        "for students to click or sign up. Do not include brand logos. If text "
        "is included, keep it minimal and readable: "
        f"'{story.headline}' and 'Start here'."
    )


def create_ai_story_image(
    story: Story,
    output_dir: Path,
    *,
    api_key: str,
    model: str = DEFAULT_OPENAI_IMAGE_MODEL,
    size: str = DEFAULT_OPENAI_IMAGE_SIZE,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = (
        output_dir
        / f"{dt.date.today().isoformat()}-{sanitize_filename(story.story_id)}-photo.png"
    )
    payload = {
        "model": model,
        "prompt": build_photographic_image_prompt(story),
        "size": size,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI image generation returned HTTP {error.code}: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to reach OpenAI image API: {error.reason}") from error

    data = json.loads(response_body)
    first_image = data.get("data", [{}])[0]
    if first_image.get("b64_json"):
        image_path.write_bytes(base64.b64decode(first_image["b64_json"]))
        return image_path

    if first_image.get("url"):
        download = urllib.request.Request(first_image["url"], method="GET")
        with urllib.request.urlopen(download, timeout=120) as response:
            image_path.write_bytes(response.read())
        return image_path

    raise RuntimeError(f"OpenAI image response did not include image data: {data}")


def create_card_story_image(story: Story, output_dir: Path) -> Path:
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


def create_story_image(
    story: Story,
    output_dir: Path,
    *,
    image_mode: str,
    openai_api_key: str | None,
    openai_image_model: str,
    openai_image_size: str,
    require_ai_image: bool,
) -> tuple[Path, str]:
    if image_mode == "card":
        return create_card_story_image(story, output_dir), "card"

    if not openai_api_key:
        if require_ai_image:
            raise RuntimeError("OPENAI_API_KEY is required when --require-ai-image is set.")
        return create_card_story_image(story, output_dir), "card_fallback_missing_openai_key"

    try:
        return (
            create_ai_story_image(
                story,
                output_dir,
                api_key=openai_api_key,
                model=openai_image_model,
                size=openai_image_size,
            ),
            "ai_photo",
        )
    except RuntimeError:
        if require_ai_image:
            raise
        return create_card_story_image(story, output_dir), "card_fallback_ai_error"


def record_story(
    history: dict[str, Any],
    story: Story,
    *,
    image_path: Path,
    image_generation: str,
    post_result: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    content_hash = story_hash(story.text)
    entry = {
        "story_id": story.story_id,
        "content_type": story.content_type,
        "content_hash": content_hash,
        "assets": story.assets,
        "word_count": story.word_count,
        "text": story.text,
        "image_path": str(image_path),
        "image_generation": image_generation,
        "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dry_run": dry_run,
        "post_response": post_result,
    }
    history.setdefault("posts", []).append(entry)
    if not dry_run:
        history.setdefault("used_hashes", []).append(content_hash)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and optionally post unique daily student employability content.",
    )
    parser.add_argument(
        "--history-path",
        default=os.getenv("DAILY_STORY_HISTORY_PATH", str(DEFAULT_HISTORY_PATH)),
        help="JSON file used to track posted content hashes.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("DAILY_STORY_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory for generated content images.",
    )
    parser.add_argument(
        "--metrics-path",
        default=os.getenv("DAILY_CONTENT_METRICS_PATH"),
        help="Optional JSON metrics file for data-led employability posts.",
    )
    parser.add_argument(
        "--image-mode",
        choices=("ai", "card"),
        default=os.getenv("DAILY_STORY_IMAGE_MODE", "ai"),
        help="Use AI photorealistic images or the local graphic card fallback.",
    )
    parser.add_argument(
        "--openai-api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key used for AI photo generation.",
    )
    parser.add_argument(
        "--openai-image-model",
        default=os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_OPENAI_IMAGE_MODEL),
        help="OpenAI image model for AI photo generation.",
    )
    parser.add_argument(
        "--openai-image-size",
        default=os.getenv("OPENAI_IMAGE_SIZE", DEFAULT_OPENAI_IMAGE_SIZE),
        help="OpenAI image size for AI photo generation.",
    )
    parser.add_argument(
        "--require-ai-image",
        action="store_true",
        help="Fail instead of falling back to the card image when AI generation fails.",
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
        help="Write dry-run output to history without marking the content as used.",
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
        metrics = load_metrics(Path(args.metrics_path) if args.metrics_path else None)
        story = choose_unused_story(history, metrics=metrics, seed=args.seed)
        image_path, image_generation = create_story_image(
            story,
            output_dir,
            image_mode=args.image_mode,
            openai_api_key=args.openai_api_key,
            openai_image_model=args.openai_image_model,
            openai_image_size=args.openai_image_size,
            require_ai_image=args.require_ai_image,
        )
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
                image_description=f"{story.content_type} from World of Interns",
            )
        except (LinkedInPostError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    if args.post or args.record_dry_run:
        record_story(
            history,
            story,
            image_path=image_path,
            image_generation=image_generation,
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
        "content_type": story.content_type,
        "assets": story.assets,
        "word_count": story.word_count,
        "content": story.text,
        "image_path": str(image_path),
        "image_generation": image_generation,
        "history_path": str(history_path),
        "recorded": args.post or args.record_dry_run,
        "post_response": post_result,
    }
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
