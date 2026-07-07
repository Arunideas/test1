#!/usr/bin/env python3
"""Recurring weekly LinkedIn series schedule for World of Interns."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklySeries:
    key: str
    label: str
    emoji: str

    @property
    def header(self) -> str:
        return f"{self.emoji} {self.label}"


WEEKLY_SERIES_SCHEDULE: tuple[WeeklySeries, ...] = (
    WeeklySeries("ai_tool_of_the_week", "AI Tool of the Week", "🛠"),
    WeeklySeries("prompt_of_the_week", "Prompt of the Week", "🎯"),
    WeeklySeries("internship_opportunities", "Internship Opportunities", "💼"),
    WeeklySeries("resume_makeover", "Resume Makeover", "📄"),
    WeeklySeries("ai_career_tip", "AI Career Tip", "🤖"),
    WeeklySeries("hiring_trends", "Hiring Trends", "📊"),
    WeeklySeries("student_success_story", "Student Success Story", "🎓"),
)

SERIES_BY_KEY: dict[str, WeeklySeries] = {
    series.key: series for series in WEEKLY_SERIES_SCHEDULE
}

SERIES_HASHTAGS: dict[str, tuple[str, ...]] = {
    "ai_tool_of_the_week": ("AIToolOfTheWeek", "ToolTuesday"),
    "prompt_of_the_week": ("PromptOfTheWeek", "PromptEngineering"),
    "internship_opportunities": ("InternshipOpportunities", "HiringNow"),
    "resume_makeover": ("ResumeMakeover", "ResumeTips"),
    "ai_career_tip": ("AICareerTip", "CareerAdvice"),
    "hiring_trends": ("HiringTrends", "JobMarket"),
    "student_success_story": ("StudentSuccess", "CareerWin"),
}


def resolve_series_for_date(day: dt.date) -> WeeklySeries:
    return WEEKLY_SERIES_SCHEDULE[day.weekday()]


def prepend_series_header(text: str, series: WeeklySeries) -> str:
    header = series.header
    body = text.strip()
    if not body:
        return header
    if body.startswith(header):
        return body
    return f"{header}\n\n{body}"
