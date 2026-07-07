#!/usr/bin/env python3
"""Create and post daily employability content to LinkedIn using AI only.

The agent selects a content brief, generates the LinkedIn caption with an OpenAI
LLM, generates a photorealistic image with OpenAI, tracks used content in a JSON
history file, and can post both to LinkedIn.
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
from weekly_linkedin_series import (
    SERIES_BY_KEY,
    SERIES_HASHTAGS,
    WeeklySeries,
    prepend_series_header,
    resolve_series_for_date,
)


DEFAULT_HISTORY_PATH = Path("daily_story_history.json")
DEFAULT_OUTPUT_DIR = Path("daily_story_output")
DEFAULT_OPENAI_TEXT_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"
DEFAULT_OPENAI_IMAGE_SIZE = "1024x1024"
DEFAULT_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
MAX_CONTENT_GENERATION_ATTEMPTS = 3
MIN_POST_WORDS = 70
MAX_POST_WORDS = 180
MAX_PROMOTIONAL_SCORE = 5
MIN_WEIGHTED_QUALITY_SCORE = 65

POST_QUALITY_WEIGHTS: dict[str, float] = {
    "educational": 0.30,
    "actionable": 0.25,
    "trustworthy": 0.20,
    "engaging": 0.15,
    "brand_mention": 0.05,
}

POST_QUALITY_ATTRIBUTES = tuple(POST_QUALITY_WEIGHTS) + ("promotional",)

VOICE_EXAMPLE_PHRASES = (
    "A final-year engineering student...",
    "A recruiter reviewing resumes...",
    "One startup founder told us...",
)

FORBIDDEN_CHARACTER_NAMES = frozenset(
    {
        "Asha",
        "Dev",
        "John",
        "Rahul",
        "Priya",
        "Meera",
        "Ravi",
        "Nisha",
        "Ibrahim",
        "Arjun",
        "Kavya",
        "Sara",
        "Neel",
    }
)

CONTENT_SYSTEM_PROMPT = """You write LinkedIn posts for World of Interns.

Voice and tone:
- Sound like a 45-year-old experienced mentor talking to students, not a professional English teacher or Cambridge essay
- Use casual spoken English. Short sentences are fine. Small grammar slips are okay if it feels real
- Avoid polished lecture words like "Furthermore", "It is imperative", "leverage synergies", "transformative journey"
- Do not use character names like Dev, John, Rahul, or Priya unless the brief clearly marks the story as fictional
- Prefer real-world phrasing like "A final-year engineering student...", "A recruiter reviewing resumes...", "One startup founder told us..."
- Sound human, specific, and scroll-stopping — not corporate or textbook

Post rules:
- Stay between WORD_MIN and WORD_MAX words
- Use all four required sections in order:
  1. Hook (1-2 short sentences)
  2. Proof (before/after, example, or short story — at least 3 sentences)
  3. Takeaway (one line that starts with "Takeaway:")
  4. Checkbox question with 3-4 options; each option on its own line starting with □
- Do not skip any section or end the post early
- Do not use labels like "Topic:", "Insight:", "Hook:", or "Proof:" except the Takeaway line
- Do not add website links or signup CTAs
- Do not include hashtags; meaningful tags are appended automatically after generation
- Use the provided pillar, brief, and metrics naturally when relevant
- For Prompt of the Week posts, include the full copy-paste prompt in quotes

Image prompt rules:
- Describe a photorealistic desk/workspace scene told through objects and screens only
- Never include readable text, words, letters, handwriting, book titles, sticky-note text, UI labels, or logos with text
- Any screens, papers, notebooks, or books must have blurred or blank text areas
- Use color blocks, charts without labels, and composition instead of typography

Quality gate — score the caption before you finalize it (0-100 each):
- educational (weight 30%)
- actionable (weight 25%)
- trustworthy (weight 20%)
- engaging (weight 15%)
- brand_mention (weight 5%)
- promotional (must be 5 or less; hard limit)

Only return a caption if promotional is 5 or less and the weighted score is strong.

Return JSON with exactly these keys:
- caption: the full LinkedIn post text ready to publish
- image_prompt: a detailed no-text photorealistic scene prompt — objects, desks, blurred screens, charts without labels; never ask for readable words on paper or screens
- quality_scores: object with numeric scores for educational, actionable, trustworthy, engaging, brand_mention, and promotional
"""

IMAGE_PROMPT_RULES = """Image generation constraints:
- Photorealistic square composition
- Absolutely no readable text, letters, numbers, handwriting, book titles, sticky-note writing, UI labels, or logos with words anywhere in the scene
- Laptop/tablet/phone screens must show blurred interfaces, abstract color blocks, or out-of-focus dashboards only
- Notebooks, resumes, and papers must be blank or have illegible blur — never ask for specific words on them
- Tell the story with objects, lighting, posture, and workspace mood only"""

IMAGE_PROMPT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"handwritten notes?", "blank notepad with pen"),
    (r"handwriting", "blank paper"),
    (r"sticky notes?(?: (?:saying|with|reading|that says)[^.]*)?", "blank yellow sticky notes"),
    (r"book titled[^.]*", "plain book with blank cover"),
    (r"headline (?:reading|showing|like|with)[^.]*", "blurred profile screen with a highlight bar"),
    (r"resume (?:for|showing|with|document)[^.]*", "laptop showing a blurred document layout"),
    (r"notepad with[^.]*", "notepad and pen on desk"),
    (r"notes about[^.]*", "desk notes"),
    (r"labeled[^.]*", "organized desk items"),
    (r"title(?:d)?[^.]*on[^.]*cover", "plain covered book"),
    (r"text on[^.]*", "visual layout on"),
    (r"reading \"[^\"]+\"", "showing a blurred screen"),
)

BASE_HASHTAGS = (
    "WorldOfInterns",
    "Internships",
    "Students",
    "CareerAdvice",
)

PILLAR_HASHTAGS: dict[str, tuple[str, ...]] = {
    "Student Employability": (
        "Employability",
        "ResumeTips",
        "InterviewPrep",
        "SkillDevelopment",
    ),
    "Hire Interns in 10 Days": (
        "Hiring",
        "Recruitment",
        "TalentAcquisition",
        "InternHiring",
    ),
    "Internship Verification": (
        "InternshipVerification",
        "ScamAlert",
        "CareerSafety",
        "VerifiedInternships",
    ),
    "Recruiter Secrets": (
        "Recruiting",
        "HiringManagers",
        "RecruiterTips",
        "JobSearch",
    ),
    "Market Intelligence": (
        "JobMarket",
        "CareerTrends",
        "SalaryInsights",
        "InternshipMarket",
    ),
    "Employer Branding": (
        "EmployerBranding",
        "TalentBrand",
        "CampusRecruiting",
        "InternshipPrograms",
    ),
    "Campus Ambassador / Job Acquisition": (
        "CampusAmbassador",
        "StudentJobs",
        "CampusPlacement",
        "EarnWhileYouLearn",
    ),
    "AI Career Survival": (
        "AICareer",
        "FutureOfWork",
        "CareerGrowth",
        "AIForStudents",
    ),
    "Learn One AI Tool Every Week": (
        "AITools",
        "LearnAI",
        "Productivity",
        "TechSkills",
    ),
    "AI Challenge of the Week": (
        "AIChallenge",
        "BuildInPublic",
        "LearningByDoing",
        "PortfolioBuilding",
    ),
    "AI Resume Upgrade": (
        "Resume",
        "AIResume",
        "JobSearch",
        "CareerPrep",
    ),
    "AI Interview Practice": (
        "InterviewTips",
        "MockInterview",
        "CommunicationSkills",
        "InterviewPrep",
    ),
    "AI Mythbusters": (
        "AIMyths",
        "TechLiteracy",
        "CareerMyths",
        "AIReality",
    ),
    "Future Skills": (
        "FutureSkills",
        "Upskilling",
        "EmergingTech",
        "CareerReady",
    ),
    "Prompt of the Week": (
        "PromptOfTheWeek",
        "PromptEngineering",
        "ChatGPTTips",
        "CareerPrompts",
    ),
    "Student Success Story": (
        "StudentSuccess",
        "CareerWin",
        "InternshipJourney",
        "ProofOfWork",
    ),
}

CONTENT_TYPE_HASHTAGS: dict[str, tuple[str, ...]] = {
    "Resume Before vs After": ("ResumeMakeover", "BeforeAndAfter"),
    "Employability Score Explained": ("EmployabilityScore", "CareerMapping"),
    "Resume Mistakes": ("ResumeMistakes", "ResumeWriting"),
    "Interview Questions": ("InterviewQuestions", "InterviewSkills"),
    "Skill Gap Analysis": ("SkillGap", "CareerPlanning"),
    "Portfolio Reviews": ("Portfolio", "ProjectShowcase"),
    "Project Ideas": ("ProjectIdeas", "BuildProjects"),
    "Career Roadmaps": ("CareerRoadmap", "CareerPlanning"),
    "Screened to shortlist": ("Shortlisting", "RecruiterInsights"),
    "Startup hiring speed": ("StartupHiring", "FastHiring"),
    "AI screening reduction": ("AIScreening", "HRTech"),
    "Unqualified intern cost": ("HiringRisk", "TalentQuality"),
    "Stipend investigation": ("InternshipStipend", "DueDiligence"),
    "Verify My Internship": ("VerifyInternship", "InternshipSafety"),
    "Scam indicators": ("InternshipScam", "StaySafe"),
    "12 second reject": ("ResumeReview", "FirstImpression"),
    "Application mistakes": ("JobApplication", "ApplySmart"),
    "What HR notices first": ("HRInsights", "RecruiterView"),
    "Top Skills This Week": ("TopSkills", "InDemandSkills"),
    "Top Hiring Cities": ("HiringCities", "JobLocations"),
    "Top Paying Internship Domains": ("InternshipPay", "HighPayingInternships"),
    "Most Applied Jobs": ("CompetitiveRoles", "ApplicationStrategy"),
    "Average Employability Score": ("EmployabilityBenchmark", "CareerMetrics"),
    "Low application count": ("JobDescription", "HiringTips"),
    "Improve your JD": ("JobDescription", "HiringCopy"),
    "Salary Benchmark": ("SalaryBenchmark", "Compensation"),
    "Campus Hiring Guide": ("CampusHiring", "UniversityRecruiting"),
    "Internship Program Design": ("InternshipProgram", "EarlyTalent"),
    "Campus Growth Partner": ("CampusGrowth", "StudentAmbassador"),
    "Earn while helping": ("StudentSideHustle", "CampusJobs"),
    "Jobs AI won't replace": ("HumanSkills", "CareerResilience"),
    "AI made developer faster": ("DeveloperProductivity", "AIAssistedCoding"),
    "AI plus Humans": ("HumanInTheLoop", "CollaborativeAI"),
    "Recruiter AI evaluation": ("AIAtWork", "WorkplaceAI"),
    "Mention AI on resume": ("ResumeAI", "AISkills"),
    "Portfolio in 30 minutes": ("QuickPortfolio", "ShipFast"),
    "AI dataset dashboard": ("DataDashboard", "AnalyticsProjects"),
    "Excel plus AI workflow": ("ExcelSkills", "DataReporting"),
    "AI workflow proof": ("WorkflowAutomation", "ProofOfWork"),
    "AI interview scoring": ("InterviewPractice", "CommunicationCoaching"),
    "Developers replaced myth": ("DeveloperCareers", "CodingCareers"),
    "Prompt engineering myth": ("PromptEngineering", "ProblemSolving"),
    "Agentic AI": ("AgenticAI", "AIAgents"),
    "MCP": ("ModelContextProtocol", "AIInfrastructure"),
    "RAG": ("RetrievalAugmentedGeneration", "AIApplications"),
    "Vector Databases": ("VectorDB", "AIML"),
}

AI_TOOL_CONTENT_TYPES = frozenset(
    {
        "ChatGPT",
        "Claude",
        "Cursor",
        "GitHub Copilot",
        "Canva AI",
        "Figma AI",
        "Perplexity",
        "Gemini",
        "Notion AI",
        "n8n",
        "Zapier AI",
    }
)

AI_TOOL_WHY_STUDENTS_SHOULD_CARE_BLOCK = """Why this matters

✓ Save 2 hours/week
✓ Improve assignments
✓ Prepare for interviews
✓ Build better projects
✓ Write better documentation"""

RESUME_MAKEOVER_CONTENT_TYPES = frozenset(
    {
        "Resume Before vs After",
        "Resume Mistakes",
        "Excel plus AI workflow",
        "AI workflow proof",
    }
)

RESUME_MAKEOVER_CONTENT_GROUPS = frozenset(
    {
        "Student Employability",
        "AI Resume Upgrade",
    }
)

AI_CAREER_TIP_CONTENT_GROUPS = frozenset(
    {
        "AI Career Survival",
        "AI Mythbusters",
        "AI Interview Practice",
        "Future Skills",
    }
)

HIRING_TRENDS_CONTENT_GROUPS = frozenset(
    {
        "Market Intelligence",
        "Employer Branding",
        "Hire Interns in 10 Days",
    }
)

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
    "intern_hiring_days": "10",
    "screening_time_saved": "42%",
    "campus_campaign_reach": "3,200",
    "bulk_recruitment_roles": "120",
    "hiring_trend_year": "2026",
    "salary_benchmark_role": "Data Analyst Intern",
    "salary_benchmark_growth": "22%",
    "students_screened": "250",
    "students_shortlisted": "12",
    "ai_screening_reduction": "80%",
    "internship_application_count": "14",
    "suspicious_stipend_amount": "₹50,000/month",
    "suspicious_hours_per_day": "2 hours/day",
    "top_skill_python": "Python",
    "top_skill_excel": "Excel",
    "top_skill_powerbi": "Power BI",
    "top_skill_java": "Java",
    "top_skill_prompt": "Prompt Engineering",
    "top_hiring_city": "Bangalore",
    "top_paying_domain": "Data Analytics",
    "most_applied_role": "Data Analyst Intern",
    "verification_checks_count": "7",
    "campus_partner_title": "Campus Growth Partner",
    "ai_speed_multiplier": "5×",
    "ai_challenge_minutes": "30",
    "ai_jobs_safe_count": "5",
    "future_skill_current": "Agentic AI",
    "future_skill_next": "MCP",
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
        "id": "student-resume-before-after",
        "content_group": "Student Employability",
        "content_type": "Resume Before vs After",
        "hook": "This profile got ignored. Nothing was wrong with it. It was just forgettable.",
        "headline": "BEFORE AFTER",
        "subhead": "One line changed everything.",
        "visual": "document",
        "setup": (
            "Most students do not have a weak resume because they lack talent. "
            "They have a weak resume because their strongest work is written like a classroom note."
        ),
        "sections": [
            "Before: 'B.Tech Student. Looking for opportunities.'",
            "After: 'Python Developer. Built inventory management software used by 120 students.'",
            "The difference is not design. It is proof.",
        ],
        "action": "Rewrite one resume line with problem, tool, action, and result.",
    },
    {
        "id": "student-employability-score-explained",
        "content_group": "Student Employability",
        "content_type": "Employability Score Explained",
        "hook": "Your employability score is not a label. It is a map.",
        "headline": "SCORE MAP",
        "subhead": "Know what to fix first.",
        "visual": "clock",
        "setup": (
            "An employability score shows readiness across resume, skills, assessments, "
            "projects, and interview confidence. The average score this cycle is "
            "{average_employability_score}."
        ),
        "sections": [
            "Before: guessing which area to fix.",
            "After: a score map showing resume, skills, projects, and interview gaps.",
            "Fix the lowest area first. One upgrade can change how recruiters read your profile.",
        ],
        "action": "Check your weakest area first instead of randomly applying everywhere.",
    },
    {
        "id": "student-resume-mistakes",
        "content_group": "Student Employability",
        "content_type": "Resume Mistakes",
        "hook": "Recruiters do not reject students. They reject unclear profiles.",
        "headline": "RESUME TRAP",
        "subhead": "Three lines kill shortlists.",
        "visual": "document",
        "setup": (
            "A recruiter opens a resume and scans for proof, signal, and fit. "
            "If those three things are hidden, the resume feels risky in seconds."
        ),
        "sections": [
            "Mistake one: 'Hardworking student' with no specific project proof.",
            "Mistake two: 'Worked on app' instead of problem, tool, and result.",
            "Mistake three: skills listed with nothing a recruiter can inspect.",
        ],
        "action": "Underline every line that proves a skill. Rewrite lines that only show participation.",
    },
    {
        "id": "student-interview-questions",
        "content_group": "Student Employability",
        "content_type": "Interview Questions",
        "hook": "The interview was going well until this answer.",
        "headline": "INTERVIEW TRAP",
        "subhead": "One answer kills trust.",
        "visual": "interview",
        "setup": (
            "A student is asked, 'Tell me about a project you are proud of.' "
            "The answer becomes a list of features. That is where interviews quietly fall apart."
        ),
        "sections": [
            "Before: explaining every screen and library without naming the problem.",
            "After: 'The problem was slow manual tracking. My role was cleanup and dashboard logic.'",
            "Recruiters test impact, ownership, and trade-offs — not memory.",
        ],
        "action": "Prepare one project answer with four parts: problem, your role, hard decision, result.",
    },
    {
        "id": "student-skill-gap-analysis",
        "content_group": "Student Employability",
        "content_type": "Skill Gap Analysis",
        "hook": "Top skills missing from resumes in {mechanical_resume_year}.",
        "headline": "SKILL GAPS",
        "subhead": "The gap nobody sees on a certificate.",
        "visual": "laptop",
        "setup": (
            "Skill gap analysis is useful only when it leads to action. "
            "The most common missing skills are: {mechanical_resume_missing_skills}."
        ),
        "sections": [
            "Before: listing software names without applied proof.",
            "After: connecting each skill to a project, analysis, or measurable output.",
            "Students who close one gap visibly move faster than students who collect more certificates.",
        ],
        "action": "Pick one missing skill and attach it to a real project line today.",
    },
    {
        "id": "student-portfolio-reviews",
        "content_group": "Student Employability",
        "content_type": "Portfolio Reviews",
        "hook": "Students with portfolios received {github_interview_multiplier} more interview calls.",
        "headline": "PORTFOLIO WINS",
        "subhead": "Proof beats claims.",
        "visual": "message",
        "setup": (
            "A resume can claim skills, but a portfolio lets recruiters inspect proof. "
            "Two clean projects with README files can outperform ten unsupported keywords."
        ),
        "sections": [
            "Before: skills listed. Nothing to inspect.",
            "After: README, screenshots, code, and one clear project outcome.",
            "A visible portfolio reduces risk for the recruiter.",
        ],
        "action": "Upload one project, write a README, add screenshots, and link it on your resume.",
    },
    {
        "id": "student-project-ideas",
        "content_group": "Student Employability",
        "content_type": "Project Ideas",
        "hook": "You do not need a perfect project. You need one visible proof.",
        "headline": "PROJECT PROOF",
        "subhead": "Start small. Ship once.",
        "visual": "rocket",
        "setup": (
            "The best student projects solve a real campus or local problem with a clear outcome. "
            "Recruiters do not need a massive app. They need evidence you can finish and explain."
        ),
        "sections": [
            "Before: waiting for the perfect idea.",
            "After: attendance tracker, expense splitter, inventory dashboard, or event registration tool.",
            "One shipped project beats five unfinished ideas on a resume.",
        ],
        "action": "Pick one campus problem and build a small solution you can demo in 60 seconds.",
    },
    {
        "id": "student-career-roadmaps",
        "content_group": "Student Employability",
        "content_type": "Career Roadmaps",
        "hook": "The difference between no interview and interview is usually one clear proof.",
        "headline": "ROADMAP",
        "subhead": "Direction beats drift.",
        "visual": "path",
        "setup": (
            "A career roadmap is not a five-year fantasy. It is a sequence of visible proofs: "
            "one role target, one skill stack, one project, one application cycle."
        ),
        "sections": [
            "Before: 'Open to any opportunity.'",
            "After: 'Data analyst intern building Excel and Python dashboards for campus problems.'",
            "Roadmaps work when each step produces something a recruiter can verify.",
        ],
        "action": "Name your target role, list three proofs you need, and build the first one this week.",
    },
    {
        "id": "hire-screened-two-fifty-twelve",
        "content_group": "Hire Interns in 10 Days",
        "content_type": "Screened to shortlist",
        "hook": "We screened {students_screened} students to shortlist {students_shortlisted}.",
        "headline": "250 TO 12",
        "subhead": "Proof before interviews.",
        "visual": "door",
        "setup": (
            "Intern hiring slows down when every resume gets equal attention. "
            "A faster process starts with role tasks, assessments, and proof signals."
        ),
        "sections": [
            "Before: 250 resumes in one inbox. No clear ranking.",
            "After: 12 candidates with role-specific proof and assessment scores.",
            "Interviews become about fit, not basic filtering.",
        ],
        "action": "Define one task the intern must perform in the first two weeks before opening applications.",
    },
    {
        "id": "hire-startups-no-weeks",
        "content_group": "Hire Interns in 10 Days",
        "content_type": "Startup hiring speed",
        "hook": "Why startups should not spend weeks hiring interns.",
        "headline": "10 DAY HIRE",
        "subhead": "Speed without chaos.",
        "visual": "clock",
        "setup": (
            "Startups lose momentum when internship hiring becomes an endless resume review cycle. "
            "The hidden cost is not just time — it is delayed work and wrong shortlists."
        ),
        "sections": [
            "Before: open role, wait three weeks, interview unprepared candidates.",
            "After: role task on day one, assessment by day three, shortlist by day five.",
            "By day {intern_hiring_days}, interviews focus on ownership and communication.",
        ],
        "action": "Replace one resume screen with one 45-minute role-specific task this week.",
    },
    {
        "id": "hire-ai-screening-eighty",
        "content_group": "Hire Interns in 10 Days",
        "content_type": "AI screening reduction",
        "hook": "How AI reduces internship screening by {ai_screening_reduction}.",
        "headline": "AI SCREENING",
        "subhead": "Find proof faster.",
        "visual": "spotlight",
        "setup": (
            "AI screening is useful only when it searches for evidence: projects, assessment "
            "performance, role fit, and communication signals. Speed without context creates faster mistakes."
        ),
        "sections": [
            "Before: manual review of every resume keyword.",
            "After: ranked shortlist by proof, skill match, and assessment evidence.",
            "Good screening compares candidates against role-specific tasks, not buzzwords.",
        ],
        "action": "Use structured inputs so AI ranks proof before scheduling interviews.",
    },
    {
        "id": "hire-unqualified-intern-cost",
        "content_group": "Hire Interns in 10 Days",
        "content_type": "Unqualified intern cost",
        "hook": "The hidden cost of unqualified interns is not the stipend.",
        "headline": "HIDDEN COST",
        "subhead": "Wrong hire, real damage.",
        "visual": "document",
        "setup": (
            "An unqualified intern costs more than salary. It costs manager time, rework, "
            "missed deadlines, and team frustration — especially in startups with no training bandwidth."
        ),
        "sections": [
            "Before: hire fast, hope they learn on the job.",
            "After: pre-assess role tasks, verify proof, then interview for fit.",
            "One wrong intern can consume more manager time than hiring the right one properly.",
        ],
        "action": "Add one role-specific assessment before your next intern interview round.",
    },
    {
        "id": "verify-unrealistic-stipend",
        "content_group": "Internship Verification",
        "content_type": "Stipend investigation",
        "hook": "This internship promised {suspicious_stipend_amount} for {suspicious_hours_per_day}.",
        "headline": "LEGIT CHECK",
        "subhead": "Let's investigate.",
        "visual": "spotlight",
        "setup": (
            "Students constantly ask: is this internship genuine? Unrealistic pay for minimal "
            "work is one of the strongest scam signals. Legitimate? Let's investigate."
        ),
        "sections": [
            "Red flag: stipend far above market for part-time remote work.",
            "Check: company website, domain age, LinkedIn presence, and HR email domain.",
            "Result options: Verified, Proceed with Caution, or Potential Scam.",
        ],
        "action": "Before accepting any offer, verify company existence, website legitimacy, and stipend realism.",
    },
    {
        "id": "verify-my-internship",
        "content_group": "Internship Verification",
        "content_type": "Verify My Internship",
        "hook": "Is this internship genuine? Send us the offer letter.",
        "headline": "VERIFY OFFER",
        "subhead": "Trust before you commit.",
        "visual": "document",
        "setup": (
            "Students can send an offer letter, company name, job description, website, and HR email. "
            "We verify company existence, website legitimacy, domain age, LinkedIn presence, "
            "Glassdoor reviews, stipend realism, and scam indicators."
        ),
        "sections": [
            "Before: accepting an offer because the stipend looked good.",
            "After: verified check across {verification_checks_count} trust signals.",
            "Outcome: Verified, Proceed with Caution, or Potential Scam.",
        ],
        "action": "Never commit to an internship you have not verified. Check before you celebrate.",
    },
    {
        "id": "verify-scam-indicators",
        "content_group": "Internship Verification",
        "content_type": "Scam indicators",
        "hook": "Three scam signals hiding in a polished internship offer.",
        "headline": "SCAM CHECK",
        "subhead": "Spot it early.",
        "visual": "message",
        "setup": (
            "Fake internships look professional until you inspect the details. "
            "Personal Gmail for HR, no company website, upfront payment requests, "
            "and unrealistic stipends are common scam indicators."
        ),
        "sections": [
            "Signal one: HR contact uses personal email, not company domain.",
            "Signal two: website created last month with no LinkedIn company page.",
            "Signal three: offer asks for payment, training fee, or sensitive documents upfront.",
        ],
        "action": "Run every offer through a verification checklist before sharing personal documents.",
    },
    {
        "id": "recruiter-rejected-twelve-seconds",
        "content_group": "Recruiter Secrets",
        "content_type": "12 second reject",
        "hook": "Why I rejected this resume in 12 seconds.",
        "headline": "12 SEC REJECT",
        "subhead": "Recruiters scan for proof first.",
        "visual": "spotlight",
        "setup": (
            "A recruiter opens a resume and scans for proof, signal, and fit. "
            "If those three things are hidden, the resume feels risky before the candidate gets a chance."
        ),
        "sections": [
            "Problem one: top half says 'hardworking student' but shows no specific skill in a real project.",
            "Problem two: project line says 'worked on app' instead of problem, tool, and result.",
            "Fix: 'Built a Python dashboard that reduced manual report time by 30%.'",
        ],
        "action": "Review your resume like a recruiter with 30 seconds. Move your strongest proof to the top.",
    },
    {
        "id": "recruiter-top-five-mistakes",
        "content_group": "Recruiter Secrets",
        "content_type": "Application mistakes",
        "hook": "Top 5 mistakes in internship applications.",
        "headline": "TOP 5 TRAPS",
        "subhead": "Fix before you apply.",
        "visual": "document",
        "setup": (
            "Most internship applications fail before the interview because the profile "
            "does not make the shortlist decision easy for HR."
        ),
        "sections": [
            "Mistake one: generic headline with no target role.",
            "Mistake two: applying everywhere instead of matching proof to role.",
            "Mistake three: no portfolio link, no project outcome, no clear skill stack.",
        ],
        "action": "Fix your headline, top project line, and role fit before sending the next application.",
    },
    {
        "id": "recruiter-what-hr-notices",
        "content_group": "Recruiter Secrets",
        "content_type": "What HR notices first",
        "hook": "What HR notices first is never your CGPA.",
        "headline": "HR SCAN",
        "subhead": "First 8 seconds.",
        "visual": "interview",
        "setup": (
            "HR does not read resumes like students do. They scan for headline clarity, "
            "project proof near the top, and whether the profile matches the role."
        ),
        "sections": [
            "First scan: headline — does it name a role and proof?",
            "Second scan: top project — is there a problem, tool, and result?",
            "Third scan: fit — does this profile match what the JD actually needs?",
        ],
        "action": "Make your headline, top project, and role target obvious in the first screen.",
    },
    {
        "id": "market-top-skills-week",
        "content_group": "Market Intelligence",
        "content_type": "Top Skills This Week",
        "hook": "Top skills this week: {top_skill_python} ↑ {top_skill_excel} ↑ {top_skill_powerbi} ↑",
        "headline": "SKILL TREND",
        "subhead": "This week’s demand.",
        "visual": "rocket",
        "setup": (
            "Skill demand shifts weekly. Right now students targeting internships should "
            "watch which skills appear most in applications and shortlists."
        ),
        "sections": [
            "Rising: {top_skill_python}, {top_skill_excel}, {top_skill_powerbi}, {top_skill_java}, {top_skill_prompt}.",
            "Before: learning randomly.",
            "After: building one project that proves the skill employers are hiring for this week.",
        ],
        "action": "Pick one rising skill and ship one small proof project this week.",
    },
    {
        "id": "market-top-hiring-cities",
        "content_group": "Market Intelligence",
        "content_type": "Top Hiring Cities",
        "hook": "Top hiring city this cycle: {top_hiring_city}.",
        "headline": "CITY SIGNAL",
        "subhead": "Where demand is moving.",
        "visual": "arrow",
        "setup": (
            "Internship demand is not evenly spread. Some cities show higher application "
            "volume, faster shortlists, and more role openings in specific domains."
        ),
        "sections": [
            "Before: applying nationally with one generic profile.",
            "After: targeting cities and roles where your proof matches local demand.",
            "{top_hiring_city} is leading internship activity in tech and analytics roles.",
        ],
        "action": "Align your target city, role, and proof instead of sending the same profile everywhere.",
    },
    {
        "id": "market-top-paying-domains",
        "content_group": "Market Intelligence",
        "content_type": "Top Paying Internship Domains",
        "hook": "Top paying internship domain this cycle: {top_paying_domain}.",
        "headline": "PAY SIGNAL",
        "subhead": "Pay follows proof.",
        "visual": "spotlight",
        "setup": (
            "Higher stipends usually follow roles with stronger business impact and clearer proof requirements. "
            "{top_paying_domain} leads when students can show dashboards, analysis, or shipped tools."
        ),
        "sections": [
            "Before: chasing stipend numbers without readiness.",
            "After: building role-ready proof in a high-demand domain.",
            "Pay benchmarks rise, but companies still hire for credible evidence.",
        ],
        "action": "Before chasing a high-paying domain, build one project that proves you can create value there.",
    },
    {
        "id": "market-most-applied-jobs",
        "content_group": "Market Intelligence",
        "content_type": "Most Applied Jobs",
        "hook": "Most applied role this week: {most_applied_role}.",
        "headline": "MOST APPLIED",
        "subhead": "Crowded lane.",
        "visual": "laptop",
        "setup": (
            "The most applied roles are also the most competitive. Students need sharper proof "
            "to stand out when hundreds apply to the same title."
        ),
        "sections": [
            "Before: applying to {most_applied_role} with a generic resume.",
            "After: one portfolio project that proves the core workflow for that role.",
            "In crowded roles, proof beats keywords.",
        ],
        "action": "If you target a popular role, show one complete workflow project — not five disconnected tools.",
    },
    {
        "id": "market-average-employability-score",
        "content_group": "Market Intelligence",
        "content_type": "Average Employability Score",
        "hook": "Average employability score this cycle: {average_employability_score}.",
        "headline": "SCORE CHECK",
        "subhead": "Readiness can be measured.",
        "visual": "clock",
        "setup": (
            "Employability becomes easier to improve when students stop treating it as a vague feeling. "
            "The average score this cycle is {average_employability_score}."
        ),
        "sections": [
            "Low scores: weak proof — skills listed without outcomes.",
            "Medium scores: projects exist, but role fit is unclear.",
            "High scores: resume clarity, assessment performance, portfolio proof, interview readiness.",
        ],
        "action": "Score yourself across resume, skills, projects, and interview answers. Fix the lowest area first.",
    },
    {
        "id": "employer-low-applications",
        "content_group": "Employer Branding",
        "content_type": "Low application count",
        "hook": "Why your internship gets only {internship_application_count} applications.",
        "headline": "14 APPS",
        "subhead": "The JD is the problem.",
        "visual": "message",
        "setup": (
            "Low application counts usually mean the JD is vague, the stipend unclear, "
            "or the role sounds like unpaid busywork. Students apply where the opportunity feels real."
        ),
        "sections": [
            "Before: 'Looking for motivated intern.' No tasks. No stipend. No learning path.",
            "After: clear tasks, stipend range, tools used, and what the intern will ship in 30 days.",
            "Better JDs attract better candidates faster.",
        ],
        "action": "Rewrite your JD with three concrete tasks, one learning outcome, and clear stipend details.",
    },
    {
        "id": "employer-improve-jd",
        "content_group": "Employer Branding",
        "content_type": "Improve your JD",
        "hook": "Your JD is not boring. It is unclear.",
        "headline": "FIX THE JD",
        "subhead": "Clarity attracts proof.",
        "visual": "document",
        "setup": (
            "Students skip JDs that read like generic HR templates. "
            "The best internship posts explain what you will do in week one, what tools you will use, "
            "and what proof you will build."
        ),
        "sections": [
            "Before: long paragraph of company history. No intern tasks.",
            "After: bullet tasks, expected outputs, mentor support, and application steps.",
            "Clarity reduces bad applications and increases strong ones.",
        ],
        "action": "Replace one vague paragraph with three task bullets and one expected deliverable.",
    },
    {
        "id": "employer-salary-benchmark",
        "content_group": "Employer Branding",
        "content_type": "Salary Benchmark",
        "hook": "{salary_benchmark_role} stipends grew {salary_benchmark_growth} — but only for role-ready candidates.",
        "headline": "PAY BENCHMARK",
        "subhead": "Market rate matters.",
        "visual": "spotlight",
        "setup": (
            "Salary benchmarks help companies compete for talent and help students understand market value. "
            "Underpaying or hiding stipend ranges pushes strong candidates away."
        ),
        "sections": [
            "Before: 'Stipend negotiable' with no range.",
            "After: transparent benchmark aligned with role tasks and market demand.",
            "Companies that publish fair ranges get stronger application quality.",
        ],
        "action": "Benchmark your stipend against role tasks and market data before posting.",
    },
    {
        "id": "employer-campus-hiring-guide",
        "content_group": "Employer Branding",
        "content_type": "Campus Hiring Guide",
        "hook": "Campus hiring fails when it measures registrations, not readiness.",
        "headline": "CAMPUS GUIDE",
        "subhead": "Reach is not readiness.",
        "visual": "conversation",
        "setup": (
            "Campus hiring campaigns can reach {campus_campaign_reach} students, but reach alone "
            "does not create a strong shortlist. The campaign needs assessment, resume review, and role matching."
        ),
        "sections": [
            "Before: webinar, form, silence.",
            "After: assessment, employability score movement, and role-specific shortlists.",
            "Strong campus hiring shows students a path from preparation to interview.",
        ],
        "action": "Design every campus campaign with a readiness score, not only an application count.",
    },
    {
        "id": "employer-internship-program-design",
        "content_group": "Employer Branding",
        "content_type": "Internship Program Design",
        "hook": "Great internship programs are designed, not improvised.",
        "headline": "PROGRAM DESIGN",
        "subhead": "Structure wins.",
        "visual": "path",
        "setup": (
            "The best internship programs define onboarding, weekly tasks, mentor check-ins, "
            "and a final deliverable. Students stay when they know what success looks like."
        ),
        "sections": [
            "Before: intern joins, waits for tasks, leaves confused.",
            "After: week-one task, mid-point review, final demo, and conversion path.",
            "Structured programs produce better work and stronger employer brand.",
        ],
        "action": "Define week-one tasks, mentor cadence, and a final deliverable before your next intern joins.",
    },
    {
        "id": "campus-growth-partner-role",
        "content_group": "Campus Ambassador / Job Acquisition",
        "content_type": "Campus Growth Partner",
        "hook": "Don't call them sales interns. Call them {campus_partner_title}.",
        "headline": "GROWTH PARTNER",
        "subhead": "Bring jobs, not pitches.",
        "visual": "rocket",
        "setup": (
            "Campus Growth Partners find startups hiring interns, contact HR, schedule demos, "
            "and bring internship opportunities to students. They build employer relationships "
            "while helping peers get hired."
        ),
        "sections": [
            "Before: 'Sales intern' with unclear targets.",
            "After: Employer Outreach Intern with clear mission — find roles, verify companies, connect HR.",
            "The role works because it helps both students and companies.",
        ],
        "action": "If you know startups hiring, you can connect them to pre-assessed student talent.",
    },
    {
        "id": "campus-earn-while-helping",
        "content_group": "Campus Ambassador / Job Acquisition",
        "content_type": "Earn while helping",
        "hook": "Want to earn while helping students get hired?",
        "headline": "EARN AND HELP",
        "subhead": "Campus Growth Partner.",
        "visual": "conversation",
        "setup": (
            "Campus Growth Partners earn by connecting verified employers with pre-assessed students. "
            "Responsibilities: find startups hiring, contact HR, schedule demos, and bring opportunities."
        ),
        "sections": [
            "Before: scrolling job boards alone.",
            "After: building a pipeline of verified internships for your campus.",
            "You grow skills in outreach, employer relations, and hiring — while helping peers.",
        ],
        "action": "Become a Campus Growth Partner and turn employer connections into internship opportunities.",
    },
{
        "id": "ai-career-jobs-wont-replace",
        "content_group": "AI Career Survival",
        "content_type": "Jobs AI won't replace",
        "hook": "5 jobs AI won't replace — and why.",
        "headline": "AI SAFE",
        "subhead": "Humans still win here.",
        "visual": "spotlight",
        "setup": (
            "Students fear AI will erase careers overnight. The sharper question is "
            "which roles still need judgment, ownership, trust, and real-world context."
        ),
        "sections": [
            "Before: 'AI will take every job.'",
            "After: roles needing client trust, physical work, ethical judgment, and cross-team leadership.",
            "AI changes the work inside jobs. It does not erase every job category.",
        ],
        "action": "Pick one role you want and learn how AI makes that role faster, not irrelevant.",
    },
    {
        "id": "ai-career-developer-five-x",
        "content_group": "AI Career Survival",
        "content_type": "AI made developer faster",
        "hook": "AI didn't replace this developer. It made them {ai_speed_multiplier} faster.",
        "headline": "5X FASTER",
        "subhead": "AI as multiplier.",
        "visual": "laptop",
        "setup": (
            "The fear story is replacement. The real story is leverage. Developers using AI "
            "well ship faster, debug faster, and document faster — without skipping thinking."
        ),
        "sections": [
            "Before: writing boilerplate, tests, and docs manually for hours.",
            "After: AI drafts, human reviews, human ships.",
            "The developer still owns architecture, trade-offs, and final quality.",
        ],
        "action": "Use AI for one repetitive task today, then review and improve the output yourself.",
    },
    {
        "id": "ai-career-plus-humans",
        "content_group": "AI Career Survival",
        "content_type": "AI plus Humans",
        "hook": "The future isn't AI vs Humans. It's AI + Humans vs Humans.",
        "headline": "AI PLUS YOU",
        "subhead": "The new competition.",
        "visual": "rocket",
        "setup": (
            "Students who ignore AI compete against students who use it well. "
            "The edge is not prompting alone. It is combining AI speed with human judgment."
        ),
        "sections": [
            "Before: manual research, manual drafts, manual analysis.",
            "After: AI-assisted research, drafts, and analysis with human verification.",
            "The winner is not the tool. It is the person who uses the tool with proof.",
        ],
        "action": "Build one project where AI helps, but your decisions and review are visible.",
    },
    {
        "id": "ai-career-recruiter-evaluation",
        "content_group": "AI Career Survival",
        "content_type": "Recruiter AI evaluation",
        "hook": "How recruiters evaluate AI-assisted work.",
        "headline": "AI PROOF",
        "subhead": "Show your judgment.",
        "visual": "interview",
        "setup": (
            "Recruiters do not reject AI use. They reject students who cannot explain "
            "what they built, what they changed, and what they verified."
        ),
        "sections": [
            "Before: 'I used ChatGPT for the project.'",
            "After: 'I used AI to draft the dashboard layout, then I validated the logic and fixed three edge cases.'",
            "Recruiters hire judgment, ownership, and explainability.",
        ],
        "action": "For every AI-assisted project, write what AI did and what you verified.",
    },
    {
        "id": "ai-career-resume-mention",
        "content_group": "AI Career Survival",
        "content_type": "Mention AI on resume",
        "hook": "Should you mention AI tools on your resume?",
        "headline": "AI ON CV",
        "subhead": "Yes, with proof.",
        "visual": "document",
        "setup": (
            "Listing 'ChatGPT' as a skill is weak. Showing an AI-assisted workflow "
            "with your review and outcome is strong."
        ),
        "sections": [
            "Before: 'Good with AI tools.'",
            "After: 'Built an automated reporting workflow using Excel + AI and validated every formula.'",
            "Mention AI when it shows how you work, not when it replaces proof.",
        ],
        "action": "Rewrite one resume line to show AI-assisted workflow plus your verification step.",
    },
    {
        "id": "ai-tool-chatgpt",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "ChatGPT",
        "hook": "This week: learn ChatGPT for real work, not random prompts.",
        "headline": "CHATGPT",
        "subhead": "One tool. One use case.",
        "visual": "laptop",
        "setup": (
            "ChatGPT is useful when you give it context, constraints, and a review step. "
            "Use it to draft, summarize, debug explanations, and rewrite project descriptions."
        ),
        "sections": [
            "Before: asking vague questions and copying answers.",
            "After: giving context, asking for options, then editing the final output yourself.",
            "Real work example: turn messy project notes into a resume bullet with metrics.",
        ],
        "action": "Take one project note and ask ChatGPT for three resume bullet options. Pick and edit the best one.",
    },
    {
        "id": "ai-tool-claude",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Claude",
        "hook": "This week: learn Claude for long-form thinking and code review.",
        "headline": "CLAUDE",
        "subhead": "Think deeper.",
        "visual": "laptop",
        "setup": (
            "Claude works well for long documents, structured reasoning, and reviewing code "
            "with explanations. Use it when you need clarity, not just speed."
        ),
        "sections": [
            "Before: reading a 20-page PDF without a plan.",
            "After: asking Claude to extract key points, risks, and action items.",
            "Real work example: review your project README before sharing it with recruiters.",
        ],
        "action": "Paste one project README into Claude and ask what is unclear to a recruiter.",
    },
    {
        "id": "ai-tool-cursor",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Cursor",
        "hook": "This week: learn Cursor to build faster without skipping understanding.",
        "headline": "CURSOR",
        "subhead": "Build with AI.",
        "visual": "laptop",
        "setup": (
            "Cursor helps you write, refactor, and debug code in context. "
            "The skill is not auto-accepting everything. It is directing the AI and reviewing changes."
        ),
        "sections": [
            "Before: stuck on setup errors for hours.",
            "After: using Cursor to fix setup, then explaining every change you kept.",
            "Real work example: build a small portfolio page and document what you changed manually.",
        ],
        "action": "Use Cursor to fix one bug, then write a one-line explanation of the root cause.",
    },
    {
        "id": "ai-tool-github-copilot",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "GitHub Copilot",
        "hook": "This week: learn GitHub Copilot for functions, tests, and boilerplate.",
        "headline": "COPILOT",
        "subhead": "Code faster.",
        "visual": "laptop",
        "setup": (
            "Copilot is strongest for repetitive code: functions, tests, parsing, and documentation. "
            "You still need to understand what it generated."
        ),
        "sections": [
            "Before: writing the same helper functions repeatedly.",
            "After: generating a draft, reading it, and editing edge cases yourself.",
            "Real work example: generate unit tests, then break one on purpose to verify they work.",
        ],
        "action": "Write one function with Copilot, then add one test case Copilot missed.",
    },
    {
        "id": "ai-tool-canva-ai",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Canva AI",
        "hook": "This week: learn Canva AI for portfolio visuals and LinkedIn posts.",
        "headline": "CANVA AI",
        "subhead": "Design faster.",
        "visual": "message",
        "setup": (
            "Canva AI helps students create clean visuals without a design degree. "
            "Use it for project screenshots, case study slides, and profile banners."
        ),
        "sections": [
            "Before: plain screenshots with no visual story.",
            "After: one project case study slide with problem, tool, and result.",
            "Real work example: turn a dashboard screenshot into a portfolio card.",
        ],
        "action": "Create one project visual in Canva AI and add it to your portfolio today.",
    },
    {
        "id": "ai-tool-figma-ai",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Figma AI",
        "hook": "This week: learn Figma AI for UI ideas and quick prototypes.",
        "headline": "FIGMA AI",
        "subhead": "Prototype fast.",
        "visual": "laptop",
        "setup": (
            "Figma AI helps you explore layouts, components, and UI flows faster. "
            "Useful for product, design, and frontend students who need visible proof."
        ),
        "sections": [
            "Before: blank canvas and no structure.",
            "After: AI-generated layout, then your edits for clarity and usability.",
            "Real work example: prototype one app screen and explain one UX decision.",
        ],
        "action": "Build one screen in Figma AI and write why you changed one element.",
    },
    {
        "id": "ai-tool-perplexity",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Perplexity",
        "hook": "This week: learn Perplexity for research with sources.",
        "headline": "PERPLEXITY",
        "subhead": "Research better.",
        "visual": "spotlight",
        "setup": (
            "Perplexity is useful when you need fast research with citations: market trends, "
            "tool comparisons, company background checks, and interview prep."
        ),
        "sections": [
            "Before: ten open tabs and no clear answer.",
            "After: one research query with sources you can verify.",
            "Real work example: research a company before an internship interview.",
        ],
        "action": "Use Perplexity to research one target company and write three interview-ready facts.",
    },
    {
        "id": "ai-tool-gemini",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Gemini",
        "hook": "This week: learn Gemini for multimodal tasks — text, images, and docs.",
        "headline": "GEMINI",
        "subhead": "More than text.",
        "visual": "laptop",
        "setup": (
            "Gemini can help analyze images, PDFs, and mixed inputs. "
            "Useful for students working with screenshots, charts, and document-heavy projects."
        ),
        "sections": [
            "Before: manually retyping data from screenshots.",
            "After: extracting structured notes from images or PDFs, then verifying accuracy.",
            "Real work example: summarize a chart screenshot into three insights.",
        ],
        "action": "Upload one project screenshot to Gemini and ask for three insights you can verify.",
    },
    {
        "id": "ai-tool-notion-ai",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Notion AI",
        "hook": "This week: learn Notion AI to organize projects and study plans.",
        "headline": "NOTION AI",
        "subhead": "Plan smarter.",
        "visual": "document",
        "setup": (
            "Notion AI helps students turn messy notes into action plans, project docs, "
            "and weekly learning trackers."
        ),
        "sections": [
            "Before: scattered notes in five apps.",
            "After: one project page with tasks, proof links, and weekly goals.",
            "Real work example: build a 7-day employability tracker in Notion.",
        ],
        "action": "Create one Notion page for your top project with tasks, links, and outcomes.",
    },
    {
        "id": "ai-tool-n8n",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "n8n",
        "hook": "This week: learn n8n to automate boring student workflows.",
        "headline": "N8N",
        "subhead": "Automate once.",
        "visual": "arrow",
        "setup": (
            "n8n lets you connect apps and automate repetitive tasks without heavy coding. "
            "Great for operations, marketing, and no-code curious students."
        ),
        "sections": [
            "Before: manually copying form responses into a sheet.",
            "After: one automation that collects, labels, and notifies you.",
            "Real work example: automate internship application tracking.",
        ],
        "action": "Automate one repetitive task this week and screenshot the workflow as proof.",
    },
    {
        "id": "ai-tool-zapier-ai",
        "content_group": "Learn One AI Tool Every Week",
        "content_type": "Zapier AI",
        "hook": "This week: learn Zapier AI to connect tools and save hours.",
        "headline": "ZAPIER AI",
        "subhead": "Connect apps.",
        "visual": "path",
        "setup": (
            "Zapier AI helps students connect forms, sheets, email, and notifications quickly. "
            "The employability signal is showing a workflow you built, not just a tool name."
        ),
        "sections": [
            "Before: manual follow-ups and missed reminders.",
            "After: one zap that moves data and sends alerts automatically.",
            "Real work example: new form entry → sheet update → reminder email.",
        ],
        "action": "Build one simple Zap and document the before/after time saved.",
    },
    {
        "id": "ai-challenge-portfolio-30",
        "content_group": "AI Challenge of the Week",
        "content_type": "Portfolio in 30 minutes",
        "hook": "Can you build a portfolio website using AI in {ai_challenge_minutes}?",
        "headline": "30 MIN BUILD",
        "subhead": "Challenge accepted?",
        "visual": "rocket",
        "setup": (
            "This week's challenge: build a portfolio website using AI in 30 minutes. "
            "The goal is not perfection. The goal is a shipped page with your projects visible."
        ),
        "sections": [
            "Before: no portfolio link on your resume.",
            "After: one live page with projects, tools, and one outcome per project.",
            "Top submissions get featured. Ship first, polish later.",
        ],
        "action": "Build one portfolio page in 30 minutes and share the link in the comments.",
    },
    {
        "id": "ai-challenge-dataset-dashboard",
        "content_group": "AI Challenge of the Week",
        "content_type": "AI dataset dashboard",
        "hook": "Use AI to analyze a dataset and create a dashboard.",
        "headline": "DATA CHALLENGE",
        "subhead": "Show your workflow.",
        "visual": "laptop",
        "setup": (
            "This week's challenge: take a public dataset, use AI to help clean and analyze it, "
            "then build a dashboard and explain one insight you verified yourself."
        ),
        "sections": [
            "Before: raw CSV and no story.",
            "After: cleaned data, one chart, one insight, one README line.",
            "Students submit entries. Top submissions get featured.",
        ],
        "action": "Analyze one dataset with AI help and post one insight you checked manually.",
    },
    {
        "id": "ai-resume-excel-workflow",
        "content_group": "AI Resume Upgrade",
        "content_type": "Excel plus AI workflow",
        "hook": "Stop writing 'Good at Excel' on your resume.",
        "headline": "AI RESUME",
        "subhead": "Show the workflow.",
        "visual": "document",
        "setup": (
            "Recruiters ignore generic tool claims. They respond to workflows with outcomes. "
            "AI-assisted reporting is employable only when you show what you built and verified."
        ),
        "sections": [
            "Before: 'Good at Excel.'",
            "After: 'Built an automated reporting workflow using Excel + AI and validated every formula.'",
            "The upgrade is proof, not tool listing.",
        ],
        "action": "Replace one tool line with one workflow line that includes AI and your review step.",
    },
    {
        "id": "ai-resume-workflow-proof",
        "content_group": "AI Resume Upgrade",
        "content_type": "AI workflow proof",
        "hook": "Your resume should show workflows, not tool names.",
        "headline": "WORKFLOW PROOF",
        "subhead": "AI plus judgment.",
        "visual": "document",
        "setup": (
            "AI resume upgrades work when they show the full chain: problem, tool, AI assist, "
            "human review, and result."
        ),
        "sections": [
            "Before: 'Used Python and ChatGPT.'",
            "After: 'Automated weekly report generation with Python + AI, then fixed edge cases manually.'",
            "Recruiters trust process and outcome, not buzzwords.",
        ],
        "action": "Rewrite one project line using this chain: problem, tool, AI assist, review, result.",
    },
    {
        "id": "ai-interview-practice-scoring",
        "content_group": "AI Interview Practice",
        "content_type": "AI interview scoring",
        "hook": "Your interview answer might sound confident. But does it score well?",
        "headline": "AI SCORE",
        "subhead": "Practice before pressure.",
        "visual": "interview",
        "setup": (
            "Students upload interview answers. AI scores confidence, clarity, communication, "
            "and technical depth. The score matters less than the pattern it reveals."
        ),
        "sections": [
            "Before: 'I think I answered well.'",
            "After: scores on confidence, clarity, communication, and technical depth.",
            "Weak clarity with high confidence is a common trap.",
        ],
        "action": "Record one 60-second project answer and score yourself on clarity and technical depth.",
    },
    {
        "id": "ai-myth-replace-developers",
        "content_group": "AI Mythbusters",
        "content_type": "Developers replaced myth",
        "hook": "❌ AI will replace all developers. ✅ AI will replace developers who don't use AI.",
        "headline": "MYTH BUST",
        "subhead": "Update the story.",
        "visual": "spotlight",
        "setup": (
            "The scary headline is total replacement. The practical headline is selective leverage. "
            "Developers who combine AI speed with strong judgment become more valuable."
        ),
        "sections": [
            "Myth: all coding jobs disappear.",
            "Reality: repetitive coding gets faster; architecture and ownership still matter.",
            "The risk is not AI. The risk is ignoring it.",
        ],
        "action": "Use AI on one coding task this week and document what you still decided yourself.",
    },
    {
        "id": "ai-myth-prompt-engineering",
        "content_group": "AI Mythbusters",
        "content_type": "Prompt engineering myth",
        "hook": "❌ Prompt Engineering is a career. ✅ Understanding business problems is a career.",
        "headline": "REAL CAREER",
        "subhead": "Problems first.",
        "visual": "message",
        "setup": (
            "Prompt tricks fade fast. Careers built on business understanding, communication, "
            "and proof last longer."
        ),
        "sections": [
            "Myth: learn prompts, get hired.",
            "Reality: learn problems, build proof, use AI to move faster.",
            "Employers hire people who solve useful problems, not people who write fancy prompts.",
        ],
        "action": "Pick one business problem and solve it with AI help, then explain the outcome plainly.",
    },
    {
        "id": "future-skill-agentic-ai",
        "content_group": "Future Skills",
        "content_type": "Agentic AI",
        "hook": "This week: Agentic AI — explained in plain English.",
        "headline": "AGENTIC AI",
        "subhead": "Future skill.",
        "visual": "rocket",
        "setup": (
            "Agentic AI means AI that can plan steps, use tools, and complete tasks with guidance. "
            "Think less 'one answer' and more 'one workflow with checkpoints.'"
        ),
        "sections": [
            "Before: asking AI one question at a time.",
            "After: giving AI a goal, tools, and review points across a workflow.",
            "Practical example: research → draft → verify → publish.",
        ],
        "action": "Run one small task as a 3-step agent workflow and review each step yourself.",
    },
    {
        "id": "future-skill-mcp",
        "content_group": "Future Skills",
        "content_type": "MCP",
        "hook": "Next week: MCP — what it is and why it matters.",
        "headline": "MCP",
        "subhead": "Connect AI to tools.",
        "visual": "path",
        "setup": (
            "MCP (Model Context Protocol) helps AI connect to external tools and data safely. "
            "In simple terms: it lets AI work with your apps instead of guessing."
        ),
        "sections": [
            "Before: AI answers from memory only.",
            "After: AI reads live data from connected tools with permission.",
            "Practical example: AI pulling project tasks from Notion or code context from GitHub.",
        ],
        "action": "Learn one MCP use case relevant to your target role and write it in one sentence.",
    },
    {
        "id": "future-skill-rag",
        "content_group": "Future Skills",
        "content_type": "RAG",
        "hook": "Next up: RAG — how AI uses your documents instead of guessing.",
        "headline": "RAG",
        "subhead": "Grounded answers.",
        "visual": "document",
        "setup": (
            "RAG (Retrieval-Augmented Generation) means AI searches your documents first, "
            "then answers using that evidence. Less hallucination. More useful work."
        ),
        "sections": [
            "Before: AI inventing facts about your project.",
            "After: AI answering from your PDFs, notes, and codebase snippets.",
            "Practical example: chat with your project README and meeting notes.",
        ],
        "action": "Try RAG on one project folder and ask one question only your docs can answer.",
    },
    {
        "id": "future-skill-vector-databases",
        "content_group": "Future Skills",
        "content_type": "Vector Databases",
        "hook": "Next: Vector Databases — the memory behind smart AI search.",
        "headline": "VECTOR DB",
        "subhead": "Search by meaning.",
        "visual": "laptop",
        "setup": (
            "Vector databases store meaning, not just keywords. They help AI find the most "
            "relevant notes, docs, or code when answering questions."
        ),
        "sections": [
            "Before: keyword search misses the right document.",
            "After: semantic search finds the closest useful chunk.",
            "Practical example: search 100 project notes and pull the best three matches.",
        ],
        "action": "Explain vector search in one sentence using a real example from your projects.",
    },
    {
        "id": "prompt-resume-bullet-upgrade",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "Resume bullet rewrite",
        "hook": "One prompt turned a vague resume line into proof recruiters actually scan.",
        "headline": "PROMPT WIN",
        "subhead": "Copy, paste, rewrite.",
        "visual": "document",
        "setup": (
            "Students often ask AI to 'improve my resume' and get generic adjectives back. "
            "This week's prompt forces problem, tool, action, and measurable result."
        ),
        "sections": [
            "Prompt: Rewrite this resume bullet using problem, tool, action, and result. Keep it under 22 words.",
            "Before: 'Worked on inventory project using Python.'",
            "After: 'Built a Python inventory tracker that cut manual stock checks by 30% for 120 users.'",
        ],
        "action": "Paste your weakest project line into the prompt and replace only that line today.",
    },
    {
        "id": "prompt-interview-project-story",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "Interview project story",
        "hook": "This prompt saved a student interview in the first two minutes.",
        "headline": "STAR PROMPT",
        "subhead": "Project answer ready.",
        "visual": "interview",
        "setup": (
            "Most students list features when asked about a project. This prompt turns the answer "
            "into problem, role, trade-off, and result in plain language."
        ),
        "sections": [
            "Prompt: Turn my project into a 45-second interview answer with problem, my role, one hard decision, and result.",
            "Before: explaining screens and libraries with no ownership.",
            "After: naming the business problem, your contribution, and one metric.",
        ],
        "action": "Run the prompt on one project before your next mock interview.",
    },
    {
        "id": "prompt-linkedin-headline",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "LinkedIn headline",
        "hook": "Your headline is doing the job of a resume summary in eight seconds.",
        "headline": "HEADLINE PROMPT",
        "subhead": "Role plus proof.",
        "visual": "spotlight",
        "setup": (
            "Generic headlines like 'B.Tech student seeking opportunities' disappear in recruiter feeds. "
            "This prompt builds role, proof, and target in one line."
        ),
        "sections": [
            "Prompt: Write a LinkedIn headline with target role, one proof project, and core tool stack in under 120 characters.",
            "Before: 'Computer Science Student | Open to Work'.",
            "After: 'Data Analyst Intern | SQL dashboard cut report time 40% | Python, Excel, Power BI'.",
        ],
        "action": "Update your headline with one proof line this week.",
    },
    {
        "id": "prompt-skill-gap-plan",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "Skill gap plan",
        "hook": "Stop collecting courses. Start closing one gap recruiters can verify.",
        "headline": "GAP PROMPT",
        "subhead": "Seven-day plan.",
        "visual": "clock",
        "setup": (
            "Students often spread effort across ten skills. This prompt converts one target role "
            "into a seven-day proof plan with one visible output."
        ),
        "sections": [
            "Prompt: For a Data Analyst Intern role, list the top 3 skill gaps on my profile and a 7-day plan to prove each with one mini project.",
            "Before: watching tutorials with nothing to show.",
            "After: one SQL dashboard, one Excel report, one short write-up recruiters can inspect.",
        ],
        "action": "Pick one gap and ship one proof artifact this week.",
    },
    {
        "id": "prompt-recruiter-outreach",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "Recruiter outreach",
        "hook": "Most cold messages get ignored because they ask for a job instead of showing fit.",
        "headline": "OUTREACH PROMPT",
        "subhead": "Short and specific.",
        "visual": "message",
        "setup": (
            "Recruiters reply to messages that make the shortlist decision easy. "
            "This prompt keeps outreach under 80 words with role fit and one proof link."
        ),
        "sections": [
            "Prompt: Write an 80-word internship outreach message with role fit, one proof project, and a polite ask for feedback.",
            "Before: 'Please find my resume attached. I am a hardworking student.'",
            "After: naming the role, one relevant project outcome, and a portfolio link.",
        ],
        "action": "Send one tailored message this week instead of a mass template.",
    },
    {
        "id": "prompt-portfolio-summary",
        "weekly_series": "prompt_of_the_week",
        "content_group": "Prompt of the Week",
        "content_type": "Portfolio summary",
        "hook": "Recruiters click portfolios when the first screen explains value fast.",
        "headline": "PORTFOLIO PROMPT",
        "subhead": "Proof above fold.",
        "visual": "document",
        "setup": (
            "Portfolio home pages often open with biography. This prompt writes a recruiter-first "
            "summary with role target, top project, and tools."
        ),
        "sections": [
            "Prompt: Write a portfolio hero section with target role, strongest project outcome, and tool stack in 3 short lines.",
            "Before: 'Hello, I am a passionate learner.'",
            "After: role, proof, and links a recruiter can scan in ten seconds.",
        ],
        "action": "Rewrite the first screen of your portfolio this week.",
    },
    {
        "id": "success-story-python-dashboard",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "Python dashboard turnaround",
        "hook": "A final-year engineering student went from zero callbacks to three interviews in ten days.",
        "headline": "STUDENT WIN",
        "subhead": "One project changed the scan.",
        "visual": "document",
        "setup": (
            "The student had coursework on the resume but no proof recruiters could inspect. "
            "They rebuilt one project line and added a live dashboard link."
        ),
        "sections": [
            "Before: 'Good knowledge of Python and SQL.'",
            "After: 'Built a sales dashboard in Python and SQL used by a college fest team.'",
            "Result: three internship interview calls in ten days after updating the top project line.",
        ],
        "action": "Pick one project and make the result visible at the top of your profile.",
    },
    {
        "id": "success-story-resume-rewrite",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "Resume rewrite win",
        "hook": "One data-analytics student stopped getting silence after fixing a single resume line.",
        "headline": "STUDENT WIN",
        "subhead": "Proof beat polish.",
        "visual": "spotlight",
        "setup": (
            "They had applied to data roles with a generic resume for weeks. "
            "Then they rewrote only the first project bullet with a measurable outcome."
        ),
        "sections": [
            "Before: 'Created reports using Excel.'",
            "After: 'Automated weekly sales reporting in Excel, saving 6 hours per week for ops team.'",
            "Result: shortlist rate improved after recruiters could verify impact in one line.",
        ],
        "action": "Rewrite your top project bullet with time saved, users served, or accuracy improved.",
    },
    {
        "id": "success-story-claude-readme",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "Claude README clarity",
        "hook": "A computer science student turned a messy GitHub README into a recruiter-friendly story.",
        "headline": "STUDENT WIN",
        "subhead": "Clarity got clicks.",
        "visual": "document",
        "setup": (
            "The project was solid but recruiters bounced because the README was long and vague. "
            "Claude helped extract problem, build, and result in five lines."
        ),
        "sections": [
            "Before: long feature list with no business problem.",
            "After: short README with problem, stack, demo link, and one metric.",
            "Result: profile views and recruiter messages picked up within a week.",
        ],
        "action": "Make your best project understandable in one screen.",
    },
    {
        "id": "success-story-github-proof",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "GitHub proof multiplier",
        "hook": "One engineering student added a public GitHub project and doubled interview interest.",
        "headline": "STUDENT WIN",
        "subhead": "Visible beats claimed.",
        "visual": "document",
        "setup": (
            "Java was listed on the resume without evidence. They published one clean repo with README, "
            "sample output, and setup steps recruiters could inspect."
        ),
        "sections": [
            "Before: skills listed with no public proof.",
            "After: one repo with README, screenshots, and a 30-second demo GIF.",
            "Result: interview requests increased after recruiters could verify the work quickly.",
        ],
        "action": "Publish one repo that proves your strongest skill this month.",
    },
    {
        "id": "success-story-interview-prep",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "Interview prep comeback",
        "hook": "A final-year student failed one interview, then fixed the answer that broke trust.",
        "headline": "STUDENT WIN",
        "subhead": "One answer changed.",
        "visual": "interview",
        "setup": (
            "Momentum dropped when they could not explain their role in a group project. "
            "So they rehearsed one ownership-focused answer with problem, decision, and result."
        ),
        "sections": [
            "Before: describing the whole team's work with no personal contribution.",
            "After: naming their module, trade-off, and measurable outcome in 45 seconds.",
            "Result: they cleared the next two interview rounds with the same project story.",
        ],
        "action": "Prepare one project answer that names your role, not the team's.",
    },
    {
        "id": "success-story-sql-gap",
        "weekly_series": "student_success_story",
        "content_group": "Student Success Story",
        "content_type": "SQL gap closed",
        "hook": "One analytics student closed a skill gap and finally matched the JD.",
        "headline": "STUDENT WIN",
        "subhead": "Proof over promise.",
        "visual": "clock",
        "setup": (
            "They kept applying to analytics internships while the profile lacked SQL proof. "
            "Then they built one public dashboard project in seven days."
        ),
        "sections": [
            "Before: 'Interested in data analytics' with no SQL artifact.",
            "After: one SQL dashboard analyzing sample sales data with documented queries.",
            "Result: replies started coming from roles that previously auto-rejected the profile.",
        ],
        "action": "Close one visible skill gap before sending the next ten applications.",
    },
]


@dataclass(frozen=True)
class Story:
    story_id: str
    text: str
    content_group: str
    content_type: str
    assets: dict[str, str]
    hook: str
    headline: str
    subhead: str
    visual: str
    word_count: int
    series_key: str
    series_label: str


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


def openai_chat_completion(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.9,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        DEFAULT_OPENAI_CHAT_URL,
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
            f"OpenAI chat completion returned HTTP {error.code}: {error_body}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to reach OpenAI chat API: {error.reason}") from error

    data = json.loads(response_body)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"OpenAI chat response did not include content: {data}")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI chat response must be a JSON object.")
    return parsed


def build_content_user_prompt(angle: dict[str, Any], *, series: WeeklySeries) -> str:
    sections = "\n".join(f"- {section}" for section in angle.get("sections", []))
    return (
        f"WORD_MIN: {MIN_POST_WORDS}\n"
        f"WORD_MAX: {MAX_POST_WORDS}\n\n"
        f"Recurring series: {series.header}\n"
        f"Content pillar: {angle.get('content_group', 'General')}\n"
        f"Content type: {angle['content_type']}\n"
        f"Hook direction: {angle['hook']}\n"
        f"Headline: {angle['headline']}\n"
        f"Subhead: {angle['subhead']}\n"
        f"Setup: {angle.get('setup', '')}\n"
        f"Proof points:\n{sections}\n"
        f"Suggested action: {angle.get('action', '')}\n"
        f"Write for today's {series.label} installment. Do not repeat the series title in the opening line.\n"
        "Voice: sound like a 45-year-old mentor talking plainly — not a polished English teacher.\n"
        "Do not use names like Dev, John, Rahul, or Priya. Use phrases like "
        + ", ".join(VOICE_EXAMPLE_PHRASES)
        + "\n"
        "Score the caption on educational, actionable, trustworthy, engaging, brand_mention, and promotional before returning it.\n"
        "Required sections: hook, proof story, Takeaway line, and 3-4 checkbox options — do not publish an incomplete post.\n"
        + (
            "Include the full copy-paste prompt in quotes before the Takeaway line.\n"
            if series.key == "prompt_of_the_week"
            else ""
        )
        + (
            "Do not include a Why this matters section or student benefit checklist; "
            "that block is appended automatically after generation.\n"
            if series.key == "ai_tool_of_the_week"
            else ""
        )
    )


def normalize_hashtag(tag: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", tag.strip().lstrip("#"))


def format_hashtag(tag: str) -> str:
    normalized = normalize_hashtag(tag)
    return f"#{normalized}" if normalized else ""


def extract_hashtags(text: str) -> set[str]:
    return {normalize_hashtag(match) for match in re.findall(r"#(\w+)", text) if normalize_hashtag(match)}


def strip_ai_tool_why_students_should_care(text: str) -> str:
    body = text.strip()
    for marker in (
        "Why Students Should Care",
        "Why this matters",
        "✓ Save 2 hours/week",
    ):
        index = body.find(marker)
        if index != -1:
            body = body[:index].rstrip()
    return body


def append_ai_tool_why_students_should_care(caption: str) -> str:
    body = strip_ai_tool_why_students_should_care(caption)
    if not body:
        return AI_TOOL_WHY_STUDENTS_SHOULD_CARE_BLOCK
    return f"{body}\n\n{AI_TOOL_WHY_STUDENTS_SHOULD_CARE_BLOCK}"


def build_hashtags_for_angle(
    angle: dict[str, Any],
    *,
    series: WeeklySeries | None = None,
    max_tags: int = 8,
) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    content_type = angle.get("content_type", "")

    def add(*candidates: str) -> None:
        for candidate in candidates:
            if len(tags) >= max_tags:
                return
            normalized = normalize_hashtag(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tags.append(normalized)

    add(*BASE_HASHTAGS[:2])
    if series is not None:
        add(*SERIES_HASHTAGS.get(series.key, ()))
    if content_type in AI_TOOL_CONTENT_TYPES:
        add(content_type.replace(" ", ""), "AITools")
    add(*CONTENT_TYPE_HASHTAGS.get(content_type, ()))
    add(*PILLAR_HASHTAGS.get(angle.get("content_group", ""), ()))
    add(*BASE_HASHTAGS[2:])
    return tags[:max_tags]


def append_hashtags_to_caption(
    caption: str,
    angle: dict[str, Any],
    *,
    series: WeeklySeries | None = None,
    max_tags: int = 8,
) -> str:
    body = caption.strip()
    if not body:
        return body

    desired = build_hashtags_for_angle(angle, series=series, max_tags=max_tags)
    existing = extract_hashtags(body)
    missing = [tag for tag in desired if tag not in existing]
    if not missing:
        return body

    hashtag_line = " ".join(format_hashtag(tag) for tag in missing)
    return f"{body}\n\n{hashtag_line}"


def parse_quality_scores(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError("OpenAI content response missing quality_scores object.")
    scores: dict[str, float] = {}
    for attribute in POST_QUALITY_ATTRIBUTES:
        if attribute not in raw:
            raise ValueError(f"OpenAI quality_scores missing {attribute}.")
        try:
            scores[attribute] = float(raw[attribute])
        except (TypeError, ValueError) as error:
            raise ValueError(f"OpenAI quality_scores.{attribute} must be numeric.") from error
    return scores


def compute_weighted_quality_score(scores: dict[str, float]) -> float:
    return round(
        sum(scores[attribute] * weight for attribute, weight in POST_QUALITY_WEIGHTS.items()),
        2,
    )


def validate_caption_voice(caption: str) -> None:
    for name in FORBIDDEN_CHARACTER_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", caption):
            raise ValueError(
                f"Caption uses character name {name!r}. Use generic phrasing like "
                f"{VOICE_EXAMPLE_PHRASES[0]}"
            )


def validate_caption_structure(
    caption: str,
    *,
    series: WeeklySeries,
) -> None:
    body = caption.strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if len(paragraphs) < 4:
        raise ValueError(
            f"Caption must include hook, proof, takeaway, and question sections; got {len(paragraphs)} blocks."
        )

    checkbox_count = body.count("□") + body.count("☐")
    if checkbox_count < 3:
        raise ValueError(
            f"Caption must include at least 3 checkbox options; got {checkbox_count}."
        )

    if not re.search(r"(?i)\btakeaway\s*:", body):
        raise ValueError('Caption must include a Takeaway line starting with "Takeaway:".')

    if series.key == "prompt_of_the_week":
        has_prompt = bool(
            re.search(r'(?i)(copy this prompt|try this prompt|prompt:|\bturn my project\b|"[^"]{15,}")', body)
        )
        if not has_prompt:
            raise ValueError("Prompt of the Week caption must include the full copy-paste prompt.")


def sanitize_image_prompt(prompt: str) -> str:
    cleaned = prompt.strip()
    for pattern, replacement in IMAGE_PROMPT_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return f"{cleaned}\n\n{IMAGE_PROMPT_RULES}"


def validate_quality_scores(scores: dict[str, float]) -> dict[str, float]:
    promotional = scores["promotional"]
    if promotional > MAX_PROMOTIONAL_SCORE:
        raise ValueError(
            f"Promotional score must be {MAX_PROMOTIONAL_SCORE} or less; got {promotional}."
        )
    weighted = compute_weighted_quality_score(scores)
    if weighted < MIN_WEIGHTED_QUALITY_SCORE:
        raise ValueError(
            f"Weighted quality score must be at least {MIN_WEIGHTED_QUALITY_SCORE}; got {weighted}."
        )
    return {
        **scores,
        "weighted_score": weighted,
        "weights": POST_QUALITY_WEIGHTS,
        "promotional_limit": MAX_PROMOTIONAL_SCORE,
    }


def generate_ai_content(
    angle: dict[str, Any],
    *,
    series: WeeklySeries,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    parsed = openai_chat_completion(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": CONTENT_SYSTEM_PROMPT},
            {"role": "user", "content": build_content_user_prompt(angle, series=series)},
        ],
    )
    caption = str(parsed.get("caption", "")).strip()
    image_prompt = str(parsed.get("image_prompt", "")).strip()
    if not caption:
        raise ValueError("OpenAI content response missing caption.")
    if not image_prompt:
        raise ValueError("OpenAI content response missing image_prompt.")
    quality_scores = validate_quality_scores(parse_quality_scores(parsed.get("quality_scores")))
    validate_caption_voice(caption)
    validate_caption_structure(caption, series=series)
    return {
        "caption": caption,
        "image_prompt": sanitize_image_prompt(image_prompt),
        "quality_scores": quality_scores,
    }


def choose_human_hook(rng: random.Random, angle: dict[str, Any]) -> str:
    hooks_by_type = {
        "Resume Before vs After": [
            "This profile got ignored. Nothing was wrong with it. It was just forgettable.",
            "The difference between no interview and interview is usually one clear proof.",
        ],
        "Employability Score Explained": [
            "Your employability score is not a label. It is a map.",
            f"{angle['hook']} This is the gap nobody sees on a certificate.",
        ],
        "Resume Mistakes": [
            "Recruiters do not reject students. They reject unclear profiles.",
            "This resume did not need a redesign. It needed one line of proof.",
        ],
        "Portfolio Reviews": [
            "The students getting more calls are not always better. They are easier to verify.",
            f"{angle['hook']} That is not a design trick. It is a trust signal.",
        ],
        "Stipend investigation": [
            f"{angle['hook']} Legitimate? Let's investigate.",
            "If the stipend looks too good for the work, pause before you celebrate.",
        ],
        "Verify My Internship": [
            "Is this internship genuine? Most students find out too late.",
            "Before you share documents, verify the company behind the offer.",
        ],
        "12 second reject": [
            "Why I rejected this resume in 12 seconds.",
            "A recruiter does not need more adjectives. They need proof.",
        ],
        "Top Skills This Week": [
            f"{angle['hook']} The market moved. Did your profile?",
        ],
        "Low application count": [
            f"{angle['hook']} The role is not invisible. The JD is.",
        ],
        "Campus Growth Partner": [
            "Don't call them sales interns. Call them Campus Growth Partners.",
            "Want to earn while helping students get hired?",
        ],
        "Jobs AI won't replace": [
            "Everyone asks which jobs AI will take. Fewer ask which jobs still need human judgment.",
        ],
        "AI made developer faster": [
            f"{angle['hook']} The fear story is replacement. The real story is leverage.",
        ],
        "Portfolio in 30 minutes": [
            f"{angle['hook']} Ship first. Polish later.",
        ],
        "Excel plus AI workflow": [
            "Stop writing 'Good at Excel.' Show the workflow.",
        ],
        "Developers replaced myth": [
            "The scary headline is total replacement. The practical headline is selective leverage.",
        ],
        "Agentic AI": [
            f"{angle['hook']} Less one answer. More one workflow with checkpoints.",
        ],
    }
    return rng.choice(hooks_by_type.get(angle["content_type"], [angle["hook"]]))


def strip_section_label(text: str) -> tuple[str | None, str]:
    for label in ("Before", "After", "Real work example", "Myth", "Reality"):
        prefix = f"{label}:"
        if text.strip().lower().startswith(prefix.lower()):
            return label, text.split(":", 1)[1].strip()
    return None, text.strip()


def build_tool_week_proof(angle: dict[str, Any]) -> str:
    sections = angle.get("sections", [])
    before = strip_section_label(sections[0])[1] if sections else ""
    after = strip_section_label(sections[1])[1] if len(sections) > 1 else ""
    example = ""
    for section in sections[2:]:
        label, value = strip_section_label(section)
        if label == "Real work example" or not label:
            example = value
            break

    tool = angle["content_type"]
    lines = [
        f"Most students open {tool} and stall at the same point:",
        before or "too much theory, not enough output.",
        "",
        "Try this instead:",
    ]
    if after:
        parts = re.split(r",\s*then\s+", after, flags=re.IGNORECASE)
        if len(parts) > 1:
            for part in parts:
                cleaned = part.strip(" .")
                if cleaned:
                    lines.append(f"→ {cleaned[0].upper()}{cleaned[1:]}")
        else:
            lines.append(f"→ {after}")
    if example:
        example = example.rstrip(".")
        lines.append(f"→ {example[0].upper()}{example[1:]}")
    return "\n".join(lines)


def build_mythbuster_proof(angle: dict[str, Any]) -> str:
    sections = angle.get("sections", [])
    lines: list[str] = []
    for section in sections[:3]:
        label, value = strip_section_label(section)
        if label == "Myth":
            lines.extend(["Myth", value, ""])
        elif label == "Reality":
            lines.extend(["Reality", value, ""])
        elif value:
            lines.append(value)
    return "\n".join(line for line in lines if line).strip()


def build_clean_before_after(angle: dict[str, Any]) -> str:
    sections = angle.get("sections", [])
    if len(sections) >= 2:
        _, before = strip_section_label(sections[0])
        _, after = strip_section_label(sections[1])
        return f"{before}\n\n↓\n\n{after}"

    if sections:
        _, fallback = strip_section_label(sections[0])
        return fallback
    return angle.get("setup", "").strip()


def build_takeaway(rng: random.Random, angle: dict[str, Any]) -> str:
    takeaways_by_group = {
        "Student Employability": [
            "One clear proof line can change how recruiters read your whole profile.",
            "You do not need a perfect profile. You need one thing that is easy to trust.",
            "Fix the weakest signal first. Everything else gets easier after that.",
        ],
        "Hire Interns in 10 Days": [
            "Speed helps only when screening starts with proof.",
            "The best shortlists come from role tasks, not keyword searches.",
            "Ten days is enough when evidence comes before interviews.",
        ],
        "Internship Verification": [
            "A good-looking offer is not the same as a verified company.",
            "Check before you celebrate.",
            "Verification saves time, money, and regret.",
        ],
        "Recruiter Secrets": [
            "Recruiters scan for proof first. Everything else is secondary.",
            "If your strongest proof is not obvious in 8 seconds, move it up.",
            "Clarity gets interviews faster than confidence alone.",
        ],
        "Market Intelligence": [
            "The market moved. Your profile should move with it.",
            "Build proof for what is hiring now, not what was hiring last year.",
            "Data only helps when it changes what you build next.",
        ],
        "Employer Branding": [
            "Students apply where the role feels real, not vague.",
            "A clearer JD often beats a bigger brand.",
            "Better applicants start with better role clarity.",
        ],
        "Campus Ambassador / Job Acquisition": [
            "One verified employer connection can open doors for an entire campus.",
            "Opportunities travel through relationships, not only job boards.",
            "Bring roles to students instead of waiting for roles to appear.",
        ],
        "AI Career Survival": [
            "The edge is not prompting harder. It is using AI with judgment and proof.",
            "AI plus you is the competition now.",
            "Show what you reviewed, not just what the tool generated.",
        ],
        "Learn One AI Tool Every Week": [
            "One explained workflow beats listing ten AI tools on your resume.",
            "Learn the tool by shipping one small example today.",
            "Recruiters remember proof, not another tool name.",
        ],
        "AI Challenge of the Week": [
            "Ship one entry this week. Momentum beats perfection.",
            "A finished example is stronger than another tutorial bookmark.",
            "Featured submissions come from finished work, not perfect plans.",
        ],
        "AI Resume Upgrade": [
            "Workflows beat tool names on a resume every time.",
            "Show what AI helped with and what you verified yourself.",
            "Replace generic skills with one outcome recruiters can trust.",
        ],
        "AI Interview Practice": [
            "Confidence without clarity still loses interviews.",
            "Practice shows the gap before the recruiter does.",
            "A clear 60-second answer beats a long unfocused one.",
        ],
        "AI Mythbusters": [
            "The practical truth hires faster than the viral fear.",
            "Careers are built on problems solved, not buzzwords repeated.",
            "Update the story before the market updates you.",
        ],
        "Future Skills": [
            "Future skills matter when you can explain them in one practical example.",
            "Learn the concept, then show one use case.",
            "Simple language plus one real example beats jargon every time.",
        ],
    }
    group = angle.get("content_group", "Student Employability")
    action = angle.get("action", "").strip()
    if action and rng.random() < 0.35:
        return action
    return rng.choice(
        takeaways_by_group.get(group, takeaways_by_group["Student Employability"])
    )


def build_natural_proof(angle: dict[str, Any]) -> str:
    group = angle.get("content_group", "")
    if group == "Learn One AI Tool Every Week":
        return build_tool_week_proof(angle)
    if group == "AI Mythbusters":
        return build_mythbuster_proof(angle)
    return build_clean_before_after(angle)


def build_before_after(angle: dict[str, Any]) -> str:
    before_after_by_type = {
        "Resume Before vs After": (
            "Before\n"
            "B.Tech Student\n"
            "Looking for opportunities\n\n"
            "↓\n\n"
            "After\n"
            "Python Developer\n"
            "Built inventory management software used by 120 students."
        ),
        "Employability Score Explained": (
            "Before\n"
            "Guessing which area to fix first.\n\n"
            "↓\n\n"
            "After\n"
            "Score map showing resume, skills, projects, and interview gaps."
        ),
        "Resume Mistakes": (
            "Before\n"
            "Hardworking student. Worked on app.\n\n"
            "↓\n\n"
            "After\n"
            "Built a Python dashboard that reduced manual report time by 30%."
        ),
        "Interview Questions": (
            "Before\n"
            "Lists every feature and library.\n\n"
            "↓\n\n"
            "After\n"
            "Problem, my role, hard decision, measurable result."
        ),
        "Skill Gap Analysis": (
            "Before\n"
            "Lists CAD, Excel, and workshops.\n\n"
            "↓\n\n"
            "After\n"
            "Designed a bracket, documented tolerances, and explained trade-offs."
        ),
        "Portfolio Reviews": (
            "Without portfolio\n"
            "Skills listed. Nothing to inspect.\n\n"
            "↓\n\n"
            "With portfolio\n"
            "README, screenshots, code, and one clear project outcome."
        ),
        "Project Ideas": (
            "Before\n"
            "Waiting for the perfect idea.\n\n"
            "↓\n\n"
            "After\n"
            "One campus problem solved and demo-ready in 60 seconds."
        ),
        "Career Roadmaps": (
            "Before\n"
            "Open to any opportunity.\n\n"
            "↓\n\n"
            "After\n"
            "Data analyst intern building dashboards for campus problems."
        ),
        "Screened to shortlist": (
            "Before\n"
            "250 resumes. No ranking.\n\n"
            "↓\n\n"
            "After\n"
            "12 candidates with role-specific proof and assessment scores."
        ),
        "Startup hiring speed": (
            "Before\n"
            "Three weeks of resume review.\n\n"
            "↓\n\n"
            "After\n"
            "Role task on day one. Shortlist by day five. Hire by day ten."
        ),
        "AI screening reduction": (
            "Before\n"
            "Manual keyword review.\n\n"
            "↓\n\n"
            "After\n"
            "Ranked shortlist by proof, assessment, and role fit."
        ),
        "Unqualified intern cost": (
            "Before\n"
            "Hire fast. Hope they learn.\n\n"
            "↓\n\n"
            "After\n"
            "Pre-assess tasks. Verify proof. Then interview."
        ),
        "Stipend investigation": (
            "Offer claims\n"
            "₹50,000/month for 2 hours/day.\n\n"
            "↓\n\n"
            "Verification\n"
            "Domain age, LinkedIn presence, HR email, stipend realism."
        ),
        "Verify My Internship": (
            "Before\n"
            "Accepting the offer because the stipend looked good.\n\n"
            "↓\n\n"
            "After\n"
            "Verified, Proceed with Caution, or Potential Scam."
        ),
        "Scam indicators": (
            "Before\n"
            "Polished offer letter. Personal Gmail. No website.\n\n"
            "↓\n\n"
            "After\n"
            "Scam signals flagged before documents are shared."
        ),
        "12 second reject": (
            "Before\n"
            "Worked on app development project.\n\n"
            "↓\n\n"
            "After\n"
            "Built login, search, and reporting flows used by 300 participants."
        ),
        "Application mistakes": (
            "Before\n"
            "Generic headline. Same resume everywhere.\n\n"
            "↓\n\n"
            "After\n"
            "Target role, top proof, and matched applications."
        ),
        "What HR notices first": (
            "Before\n"
            "CGPA at the top. Projects at the bottom.\n\n"
            "↓\n\n"
            "After\n"
            "Headline, top project, and role fit visible in 8 seconds."
        ),
        "Top Skills This Week": (
            "Before\n"
            "Learning randomly.\n\n"
            "↓\n\n"
            "After\n"
            "One project proving the skill employers want this week."
        ),
        "Low application count": (
            "Before\n"
            "Looking for motivated intern.\n\n"
            "↓\n\n"
            "After\n"
            "Three tasks, stipend range, tools, and a 30-day deliverable."
        ),
        "Improve your JD": (
            "Before\n"
            "Long company history. No intern tasks.\n\n"
            "↓\n\n"
            "After\n"
            "Task bullets, expected outputs, mentor support, clear steps."
        ),
        "Campus Growth Partner": (
            "Before\n"
            "Sales intern with unclear targets.\n\n"
            "↓\n\n"
            "After\n"
            "Employer Outreach Intern bringing verified roles to campus."
        ),
        "Earn while helping": (
            "Before\n"
            "Scrolling job boards alone.\n\n"
            "↓\n\n"
            "After\n"
            "Building a pipeline of verified internships for your campus."
        ),
        "Jobs AI won't replace": (
            "Before\n"
            "AI will take every job.\n\n"
            "↓\n\n"
            "After\n"
            "Focus on roles needing judgment, trust, ownership, and real-world context."
        ),
        "AI made developer faster": (
            "Before\n"
            "Writing boilerplate, tests, and docs manually for hours.\n\n"
            "↓\n\n"
            "After\n"
            "AI drafts. Human reviews. Human ships."
        ),
        "AI plus Humans": (
            "Before\n"
            "Manual research, drafts, and analysis.\n\n"
            "↓\n\n"
            "After\n"
            "AI-assisted speed with human verification and proof."
        ),
        "Recruiter AI evaluation": (
            "Before\n"
            "I used ChatGPT for the project.\n\n"
            "↓\n\n"
            "After\n"
            "AI drafted the layout. I validated logic and fixed three edge cases."
        ),
        "Mention AI on resume": (
            "Before\n"
            "Good with AI tools.\n\n"
            "↓\n\n"
            "After\n"
            "Built an automated reporting workflow using Excel + AI and validated every formula."
        ),
        "ChatGPT": (
            "Before\n"
            "Vague prompts. Copied answers.\n\n"
            "↓\n\n"
            "After\n"
            "Context, options, edit, and one resume bullet with metrics."
        ),
        "Portfolio in 30 minutes": (
            "Before\n"
            "No portfolio link on your resume.\n\n"
            "↓\n\n"
            "After\n"
            "One live page with projects, tools, and outcomes."
        ),
        "AI dataset dashboard": (
            "Before\n"
            "Raw CSV and no story.\n\n"
            "↓\n\n"
            "After\n"
            "Cleaned data, one chart, one insight, one README line."
        ),
        "Excel plus AI workflow": (
            "Before\n"
            "Good at Excel.\n\n"
            "↓\n\n"
            "After\n"
            "Built an automated reporting workflow using Excel + AI and validated every formula."
        ),
        "AI workflow proof": (
            "Before\n"
            "Used Python and ChatGPT.\n\n"
            "↓\n\n"
            "After\n"
            "Automated weekly reports with Python + AI, then fixed edge cases manually."
        ),
        "AI interview scoring": (
            "Before\n"
            "I think I answered well.\n\n"
            "↓\n\n"
            "After\n"
            "Scored on confidence, clarity, communication, and technical depth."
        ),
        "Developers replaced myth": (
            "Myth\n"
            "AI will replace all developers.\n\n"
            "↓\n\n"
            "Reality\n"
            "AI will replace developers who do not use AI."
        ),
        "Prompt engineering myth": (
            "Myth\n"
            "Prompt Engineering is a career.\n\n"
            "↓\n\n"
            "Reality\n"
            "Understanding business problems is a career."
        ),
        "Agentic AI": (
            "Before\n"
            "One question at a time.\n\n"
            "↓\n\n"
            "After\n"
            "Goal, tools, review points across a workflow."
        ),
        "MCP": (
            "Before\n"
            "AI answers from memory only.\n\n"
            "↓\n\n"
            "After\n"
            "AI reads live data from connected tools with permission."
        ),
        "RAG": (
            "Before\n"
            "AI inventing facts about your project.\n\n"
            "↓\n\n"
            "After\n"
            "AI answering from your PDFs, notes, and codebase snippets."
        ),
        "Vector Databases": (
            "Before\n"
            "Keyword search misses the right document.\n\n"
            "↓\n\n"
            "After\n"
            "Semantic search finds the closest useful chunk."
        ),
    }
    if angle["content_type"] in before_after_by_type:
        return before_after_by_type[angle["content_type"]]
    return build_clean_before_after(angle)


def build_pillar_question(angle: dict[str, Any]) -> str:
    questions_by_group = {
        "Student Employability": (
            "What's holding back your employability score?\n\n"
            "□ Headline\n"
            "□ Resume\n"
            "□ Projects\n"
            "□ Skills\n"
            "□ Interview answers"
        ),
        "Hire Interns in 10 Days": (
            "What's slowing your intern hiring?\n\n"
            "□ JD clarity\n"
            "□ Screening time\n"
            "□ Assessment quality\n"
            "□ Shortlist accuracy\n"
            "□ Interview bandwidth"
        ),
        "Internship Verification": (
            "Have you seen a suspicious internship offer?\n\n"
            "□ Unrealistic stipend\n"
            "□ No company website\n"
            "□ Personal email only\n"
            "□ Upfront payment\n"
            "□ No LinkedIn presence"
        ),
        "Recruiter Secrets": (
            "What's your weakest section?\n\n"
            "□ Headline\n"
            "□ Resume\n"
            "□ Projects\n"
            "□ Skills\n"
            "□ Experience"
        ),
        "Market Intelligence": (
            "Which skill are you building this week?\n\n"
            "□ Python\n"
            "□ Excel\n"
            "□ Power BI\n"
            "□ SQL\n"
            "□ Communication"
        ),
        "Employer Branding": (
            "What would improve your internship JD first?\n\n"
            "□ Salary clarity\n"
            "□ Role tasks\n"
            "□ Learning path\n"
            "□ Application process\n"
            "□ Brand story"
        ),
        "Campus Ambassador / Job Acquisition": (
            "Would you become a Campus Growth Partner?\n\n"
            "□ Yes, I know startups hiring\n"
            "□ Yes, I want to earn while helping\n"
            "□ Maybe, tell me more\n"
            "□ Not now"
        ),
        "AI Career Survival": (
            "How are you adapting to AI at work?\n\n"
            "□ Learning AI tools\n"
            "□ Showing AI-assisted proof\n"
            "□ Ignoring AI for now\n"
            "□ Worried about replacement\n"
            "□ Already using AI daily"
        ),
        "Learn One AI Tool Every Week": (
            "Which AI tool are you learning this week?\n\n"
            "□ ChatGPT\n"
            "□ Claude\n"
            "□ Cursor\n"
            "□ GitHub Copilot\n"
            "□ Other"
        ),
        "AI Challenge of the Week": (
            "Would you try this week's AI challenge?\n\n"
            "□ Yes, I'll submit\n"
            "□ Maybe, need more time\n"
            "□ Already building\n"
            "□ Not this week"
        ),
        "AI Resume Upgrade": (
            "Which resume line needs an AI workflow upgrade?\n\n"
            "□ Excel / Sheets\n"
            "□ Python / coding\n"
            "□ Design / portfolio\n"
            "□ Research / analysis\n"
            "□ Communication"
        ),
        "AI Interview Practice": (
            "Which interview skill needs the most practice?\n\n"
            "□ Confidence\n"
            "□ Clarity\n"
            "□ Communication\n"
            "□ Technical depth\n"
            "□ All of the above"
        ),
        "AI Mythbusters": (
            "Which AI myth did you believe recently?\n\n"
            "□ AI replaces all jobs\n"
            "□ Prompt engineering is enough\n"
            "□ AI means no learning\n"
            "□ AI use hurts your resume\n"
            "□ None of these"
        ),
        "Future Skills": (
            "Which future skill should we explain next?\n\n"
            "□ Agentic AI\n"
            "□ MCP\n"
            "□ RAG\n"
            "□ Vector Databases\n"
            "□ Something else"
        ),
    }
    return questions_by_group.get(
        angle.get("content_group", "Student Employability"),
        (
            "What's the first thing you'd change?\n\n"
            "□ Headline\n"
            "□ Resume\n"
            "□ Projects\n"
            "□ Skills\n"
            "□ Experience"
        ),
    )


def build_curiosity_visual(angle: dict[str, Any]) -> str:
    scenes_by_type = {
        "Resume Before vs After": (
            "Split-screen recruiter view. Left: plain profile labeled 'Ignored'. "
            "Right: upgraded profile labeled 'Interview' with one project proof highlighted."
        ),
        "Employability Score Explained": (
            "Employability score dashboard on a laptop: score meter, red gap area, "
            "and one highlighted section labeled 'Projects'."
        ),
        "Resume Mistakes": (
            "Recruiter desk scene. A resume stamped 'REJECTED' with a sticky note: "
            "'Too vague'. A second resume has one project line highlighted."
        ),
        "Interview Questions": (
            "Interview room whiteboard with four boxes: problem, role, decision, result. "
            "One answer sheet crossed out for listing features instead of impact."
        ),
        "Skill Gap Analysis": (
            "Resume on a desk with missing skill tags floating above it. "
            "Use an audit-board style with red markers on gaps."
        ),
        "Portfolio Reviews": (
            "Laptop dashboard: 'Applications sent: 84' and 'Replies: 3'. "
            "A portfolio link card glows beside a rejected resume stack."
        ),
        "Project Ideas": (
            "Student desk with sticky notes of small project ideas and one laptop "
            "showing a simple shipped dashboard labeled 'Demo ready'."
        ),
        "Career Roadmaps": (
            "Roadmap board with four steps: role target, skill stack, project, application. "
            "The 'proof' step is circled in red."
        ),
        "Screened to shortlist": (
            "Recruiter desk with 250 resume printouts and a shortlist tray labeled '12'. "
            "Assessment scorecards sit on top of the selected stack."
        ),
        "Startup hiring speed": (
            "10-day hiring timeline board: Day 1 role task, Day 3 assessment, "
            "Day 5 shortlist, Day 10 intern selected."
        ),
        "AI screening reduction": (
            "AI screening dashboard sorting candidate cards by proof and assessment. "
            "Show a recruiter reviewing a clear shortlist, not robot imagery."
        ),
        "Unqualified intern cost": (
            "Manager desk with rework notes, missed deadline sticky notes, and an "
            "intern folder labeled 'Wrong hire'. Mood should feel costly and tense."
        ),
        "Stipend investigation": (
            "Internship offer letter on a desk promising unrealistic pay. "
            "Magnifying glass over stipend amount with verification checklist nearby."
        ),
        "Verify My Internship": (
            "Verification desk with offer letter, company website screenshot, "
            "domain age check, LinkedIn page, and three result stamps: "
            "Verified, Caution, Scam."
        ),
        "Scam indicators": (
            "Investigation board with red flags: personal Gmail, new domain, "
            "upfront payment request, and no LinkedIn company page."
        ),
        "12 second reject": (
            "Recruiter monitor with an 8-second timer. Resume top half highlighted "
            "showing vague headline and missing project proof."
        ),
        "Application mistakes": (
            "Application inbox with five identical generic profiles and one standout "
            "profile with a clear headline and project proof circled."
        ),
        "What HR notices first": (
            "HR scan screen highlighting headline, top project, and role fit in order. "
            "CGPA section faded into the background."
        ),
        "Top Skills This Week": (
            "Market intelligence screen showing rising skills with up arrows: "
            "Python, Excel, Power BI, Java, Prompt Engineering."
        ),
        "Top Hiring Cities": (
            "Map-style hiring dashboard with one city highlighted as top demand "
            "and internship role tags pinned around it."
        ),
        "Top Paying Internship Domains": (
            "Salary benchmark chart beside two profiles: one with proof, one without. "
            "The proof profile has a brighter opportunity marker."
        ),
        "Most Applied Jobs": (
            "Job board screen showing one role with hundreds of applications and "
            "a warning tag: 'Proof required to stand out'."
        ),
        "Average Employability Score": (
            "Score distribution dashboard showing average employability score with "
            "breakdown bars for resume, skills, projects, and interviews."
        ),
        "Low application count": (
            "Internship posting with '14 applications' counter beside a vague JD. "
            "An improved JD draft nearby shows task bullets and stipend range."
        ),
        "Improve your JD": (
            "Two JD printouts side by side. Left: long company history, no tasks. "
            "Right: task bullets, deliverables, and stipend range highlighted."
        ),
        "Salary Benchmark": (
            "Stipend benchmark chart on a recruiter desk with role tasks pinned "
            "beside pay ranges. Transparent range beats 'negotiable'."
        ),
        "Campus Hiring Guide": (
            "Campus hiring command center: registrations, assessment completion, "
            "and employability score movement on a large screen."
        ),
        "Internship Program Design": (
            "Program design board: week-one task, mentor check-ins, mid-point review, "
            "final demo, and conversion path."
        ),
        "Campus Growth Partner": (
            "Campus ambassador desk connecting startup HR contacts to student talent. "
            "Badge reads 'Campus Growth Partner', not 'Sales Intern'."
        ),
        "Earn while helping": (
            "Student connecting employers to pre-assessed peers on a laptop. "
            "Pipeline board shows verified internships brought to campus."
        ),
    }
    scenes_by_group = {
        "Hire Interns in 10 Days": (
            "Recruiter planning board with a bold 10-day hiring timeline, "
            "assessment cards, and a shortlist tray on the desk."
        ),
        "Internship Verification": (
            "Investigation desk with offer letter, website check, domain age, "
            "LinkedIn page, and verification result stamps."
        ),
        "Market Intelligence": (
            "Market intelligence dashboard with trend arrows, city demand map, "
            "and employability score distribution on one screen."
        ),
        "Employer Branding": (
            "Employer desk with two JD versions, application counter, and stipend "
            "benchmark chart showing how clarity changes applicant quality."
        ),
        "AI Career Survival": (
            "Split desk scene: left shows 'AI vs Humans' headline crossed out, "
            "right shows 'AI + Humans' with a developer workflow and review checklist."
        ),
        "Learn One AI Tool Every Week": (
            "Student desk with one AI tool open on laptop, sticky notes showing "
            "a real work use case, and a before/after output comparison."
        ),
        "AI Challenge of the Week": (
            "Challenge board with timer showing 30 minutes, a portfolio website "
            "in progress on laptop, and a 'Submit entry' card."
        ),
        "AI Resume Upgrade": (
            "Resume on desk with 'Good at Excel' crossed out and replaced by "
            "'Built automated reporting workflow using Excel + AI' highlighted."
        ),
        "AI Interview Practice": (
            "Interview practice screen scoring confidence, clarity, communication, "
            "and technical depth with one weak area circled in red."
        ),
        "AI Mythbusters": (
            "Myth-buster board with red X myths and green check realities side by side, "
            "investigative sticky-note style."
        ),
        "Future Skills": (
            "Future skills timeline board: Agentic AI, MCP, RAG, Vector Databases "
            "with simple plain-English labels and one practical example each."
        ),
    }
    return scenes_by_type.get(
        angle["content_type"],
        scenes_by_group.get(
            angle.get("content_group", ""),
            (
                "Curiosity-driven employability evidence scene. Use objects that tell "
                "the story: resumes, sticky notes, dashboards, scorecards, rejected "
                "applications, project proof, and highlighted gaps. Make the viewer ask "
                "'why did this happen?' before reading the caption."
            ),
        ),
    )


def build_insight(rng: random.Random, angle: dict[str, Any], *, student_name: str) -> str:
    proof_lines_by_group = {
        "Student Employability": [
            "Same student. Different signal.",
            "The skill was already there. The proof was missing.",
            "Nothing fancy. Just easier to trust.",
        ],
        "Hire Interns in 10 Days": [
            "Same role. Different screening.",
            "Speed without proof creates expensive mistakes.",
            "The shortlist gets better when evidence comes first.",
        ],
        "Internship Verification": [
            "Same offer letter. Different outcome after verification.",
            "A polished PDF is not proof of a real company.",
            "Verify first. Celebrate later.",
        ],
        "Recruiter Secrets": [
            "Same profile. Different first impression.",
            "Recruiters do not read resumes. They scan for proof.",
            "Clarity beats confidence in the first 12 seconds.",
        ],
        "Market Intelligence": [
            "Same market. Different preparation.",
            "Demand moves weekly. Profiles should move with it.",
            "Data is useful only when it changes what you build next.",
        ],
        "Employer Branding": [
            "Same role. Different response rate.",
            "Students apply where the opportunity feels real.",
            "Clarity in the JD changes applicant quality.",
        ],
        "Campus Ambassador / Job Acquisition": [
            "Same campus. Different pipeline.",
            "Opportunities come from relationships, not job boards alone.",
            "One verified employer connection can help dozens of students.",
        ],
        "AI Career Survival": [
            "Same career. Different leverage.",
            "AI is not the competition. AI plus you is.",
            "The edge is judgment, not just prompting.",
        ],
        "Learn One AI Tool Every Week": [
            "Same week. Different skill.",
            "One tool learned with proof beats ten tools listed on a resume.",
            "Real work examples make AI tools employable.",
        ],
        "AI Challenge of the Week": [
            "Same time box. Different outcome.",
            "A shipped project in 30 minutes beats a perfect plan never started.",
            "Challenges turn AI curiosity into visible proof.",
        ],
        "AI Resume Upgrade": [
            "Same tool. Different resume line.",
            "Workflows beat tool names.",
            "Show what AI helped and what you verified.",
        ],
        "AI Interview Practice": [
            "Same answer. Different score.",
            "Confidence without clarity still fails interviews.",
            "Practice reveals the gap before recruiters do.",
        ],
        "AI Mythbusters": [
            "Same headline. Different truth.",
            "Scary myths spread fast. Practical truths hire faster.",
            "Update the story before the market updates you.",
        ],
        "Future Skills": [
            "Same future. Different preparation.",
            "Future skills matter only when you can explain them simply.",
            "Learn the concept, then show one practical example.",
        ],
    }
    insight_lines_by_group = {
        "Student Employability": (
            f"For a student like {student_name}, this is usually the difference between "
            "being skipped and being understood."
        ),
        "Hire Interns in 10 Days": (
            "For HR teams and founders, this is usually the difference between "
            "three weeks of screening and a trusted shortlist in ten days."
        ),
        "Internship Verification": (
            "For students evaluating offers, this is the difference between "
            "trusting a stipend number and trusting a verified company."
        ),
        "Recruiter Secrets": (
            f"For a student like {student_name}, this is usually the difference between "
            "a profile that gets scanned and a profile that gets shortlisted."
        ),
        "Market Intelligence": (
            "For students preparing this week, this is the difference between "
            "learning randomly and building proof the market is actually hiring for."
        ),
        "Employer Branding": (
            "For companies posting internships, this is usually the difference between "
            "fourteen applications and a stronger, better-matched pipeline."
        ),
        "Campus Ambassador / Job Acquisition": (
            f"For a student like {student_name}, this is the difference between "
            "waiting for roles and bringing verified opportunities to campus."
        ),
        "AI Career Survival": (
            f"For a student like {student_name}, this is the difference between "
            "fearing AI and using it with proof, judgment, and ownership."
        ),
        "Learn One AI Tool Every Week": (
            f"For a student like {student_name}, this is the difference between "
            "listing AI tools and showing one real workflow you can explain."
        ),
        "AI Challenge of the Week": (
            "For students building proof this week, this is the difference between "
            "watching AI demos and shipping one entry worth featuring."
        ),
        "AI Resume Upgrade": (
            f"For a student like {student_name}, this is the difference between "
            "a tool list and a resume line that shows AI-assisted work plus review."
        ),
        "AI Interview Practice": (
            f"For a student like {student_name}, this is the difference between "
            "thinking you sound confident and scoring well on clarity and depth."
        ),
        "AI Mythbusters": (
            "For students entering the AI era, this is the difference between "
            "viral fear and the practical truth recruiters actually hire for."
        ),
        "Future Skills": (
            "For students preparing for next year's market, this is the difference between "
            "buzzword collecting and understanding one future skill with a real example."
        ),
    }
    group = angle.get("content_group", "Student Employability")
    proof_line = rng.choice(
        proof_lines_by_group.get(group, proof_lines_by_group["Student Employability"])
    )
    insight_line = insight_lines_by_group.get(
        group, insight_lines_by_group["Student Employability"]
    )
    return f"{proof_line}\n\n{insight_line}"


def build_content_assets(
    rng: random.Random,
    angle: dict[str, Any],
    *,
    student_name: str,
) -> dict[str, str]:
    del student_name
    hook = choose_human_hook(rng, angle)
    proof = build_natural_proof(angle)
    takeaway = build_takeaway(rng, angle)
    visual = build_curiosity_visual(angle)
    question = build_pillar_question(angle)
    return {
        "hook": hook,
        "proof": proof,
        "insight": takeaway,
        "visual": visual,
        "question": question,
    }


def format_content_text(assets: dict[str, str]) -> str:
    return (
        f"{assets['hook']}\n\n"
        f"{assets['proof']}\n\n"
        f"{assets['insight']}\n\n"
        f"{assets['question']}"
    )


def build_story(
    rng: random.Random,
    angle: dict[str, Any],
    *,
    series: WeeklySeries,
    metrics: dict[str, str],
    api_key: str,
    text_model: str,
) -> Story:
    del rng
    angle = render_content_angle(angle, metrics)
    last_error: Exception | None = None
    for _ in range(MAX_CONTENT_GENERATION_ATTEMPTS):
        try:
            generated = generate_ai_content(
                angle,
                series=series,
                api_key=api_key,
                model=text_model,
            )
            caption_body = generated["caption"]
            count = word_count(caption_body)
            if not MIN_POST_WORDS <= count <= MAX_POST_WORDS:
                raise ValueError(
                    f"Generated story must be between {MIN_POST_WORDS} and "
                    f"{MAX_POST_WORDS} words; got {count}."
                )
            if series.key == "ai_tool_of_the_week":
                caption_body = append_ai_tool_why_students_should_care(caption_body)
            caption = append_hashtags_to_caption(caption_body, angle, series=series)
            caption = prepend_series_header(caption, series)
            assets = {
                "caption": caption,
                "visual": generated["image_prompt"],
                "generation": "openai_llm",
                "prompt_brief": angle["id"],
                "series_key": series.key,
                "series_label": series.label,
                "quality_scores": generated["quality_scores"],
            }
            unique_id = f"{angle['id']}-{story_hash(caption)[:12]}"
            return Story(
                story_id=unique_id,
                text=caption,
                content_group=angle.get("content_group", "General"),
                content_type=angle["content_type"],
                assets=assets,
                hook=angle["hook"],
                headline=angle["headline"],
                subhead=angle["subhead"],
                visual=angle["visual"],
                word_count=count,
                series_key=series.key,
                series_label=series.label,
            )
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            continue
    raise ValueError(
        f"Failed to generate AI content for {angle['id']}: {last_error}"
    )


def angle_matches_series(angle: dict[str, Any], series: WeeklySeries) -> bool:
    if angle.get("weekly_series") == series.key:
        return True

    group = angle.get("content_group", "")
    content_type = angle.get("content_type", "")

    if series.key == "ai_tool_of_the_week":
        return group == "Learn One AI Tool Every Week"
    if series.key == "prompt_of_the_week":
        return group == "Prompt of the Week"
    if series.key == "resume_makeover":
        return (
            content_type in RESUME_MAKEOVER_CONTENT_TYPES
            or (
                group in RESUME_MAKEOVER_CONTENT_GROUPS
                and content_type
                in {
                    "Resume Before vs After",
                    "Resume Mistakes",
                    "Portfolio Reviews",
                }
            )
        )
    if series.key == "ai_career_tip":
        return group in AI_CAREER_TIP_CONTENT_GROUPS
    if series.key == "hiring_trends":
        return group in HIRING_TRENDS_CONTENT_GROUPS
    if series.key == "student_success_story":
        return group == "Student Success Story"
    return False


def filter_angles_for_series(series: WeeklySeries) -> list[dict[str, Any]]:
    return [angle for angle in CONTENT_ANGLES if angle_matches_series(angle, series)]


def choose_unused_story(
    history: dict[str, Any],
    *,
    series: WeeklySeries,
    report_date: dt.date,
    metrics: dict[str, str],
    api_key: str,
    text_model: str,
    seed: int | None = None,
) -> Story:
    used_hashes = set(history.get("used_hashes", []))
    eligible = filter_angles_for_series(series)
    if not eligible:
        raise RuntimeError(f"No content angles configured for {series.label}.")

    week_number, _, _ = report_date.isocalendar()
    seed_source = f"{week_number}:{series.key}:{seed or 0}"
    rng = random.Random(int(hashlib.sha256(seed_source.encode()).hexdigest()[:16], 16))
    angles = list(eligible)
    rng.shuffle(angles)
    errors: list[str] = []
    for angle in angles:
        try:
            story = build_story(
                rng,
                angle,
                series=series,
                metrics=metrics,
                api_key=api_key,
                text_model=text_model,
            )
        except ValueError as error:
            errors.append(str(error))
            continue
        if story_hash(story.text) not in used_hashes:
            return story
    detail = errors[-1] if errors else "No unused content available."
    raise RuntimeError(
        f"Could not create a new unused story for {series.label} after AI generation attempts. {detail}"
    )


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
    llm_prompt = story.assets.get("visual", "").strip()
    if llm_prompt:
        return sanitize_image_prompt(llm_prompt)
    raise ValueError("AI image prompt is missing from generated story assets.")


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
    api_key: str,
    openai_image_model: str,
    openai_image_size: str,
) -> tuple[Path, str]:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for AI image generation.")
    return (
        create_ai_story_image(
            story,
            output_dir,
            api_key=api_key,
            model=openai_image_model,
            size=openai_image_size,
        ),
        "ai_photo",
    )


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
        "content_group": story.content_group,
        "content_type": story.content_type,
        "series_key": story.series_key,
        "series_label": story.series_label,
        "quality_scores": story.assets.get("quality_scores"),
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
        "--openai-api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key required for AI caption and image generation.",
    )
    parser.add_argument(
        "--openai-text-model",
        default=os.getenv("OPENAI_TEXT_MODEL", DEFAULT_OPENAI_TEXT_MODEL),
        help="OpenAI chat model for LinkedIn caption generation.",
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
        "--seed",
        type=int,
        help="Optional random seed for repeatable dry-run testing.",
    )
    parser.add_argument(
        "--date",
        help="Override today's date (YYYY-MM-DD) to select the weekly series.",
    )
    parser.add_argument(
        "--series",
        choices=tuple(SERIES_BY_KEY),
        help="Override the weekly series instead of using today's schedule.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when today's series is handled by another agent.",
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
    report_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    series = SERIES_BY_KEY[args.series] if args.series else resolve_series_for_date(report_date)

    if series.key == "internship_opportunities" and not args.force:
        print(
            json.dumps(
                {
                    "dry_run": not args.post,
                    "skipped": True,
                    "report_date": report_date.isoformat(),
                    "series_key": series.key,
                    "series_label": series.label,
                    "reason": (
                        "Wednesday is Internship Opportunities day. "
                        "Run daily_internship_intelligence_agent.py instead."
                    ),
                },
                indent=2,
            )
        )
        return 0

    try:
        if not args.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for AI caption and image generation.")
        history = load_history(history_path)
        metrics = load_metrics(Path(args.metrics_path) if args.metrics_path else None)
        story = choose_unused_story(
            history,
            series=series,
            report_date=report_date,
            metrics=metrics,
            api_key=args.openai_api_key,
            text_model=args.openai_text_model,
            seed=args.seed,
        )
        image_path, image_generation = create_story_image(
            story,
            output_dir,
            api_key=args.openai_api_key,
            openai_image_model=args.openai_image_model,
            openai_image_size=args.openai_image_size,
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
        "report_date": report_date.isoformat(),
        "series_key": story.series_key,
        "series_label": story.series_label,
        "story_id": story.story_id,
        "content_group": story.content_group,
        "content_type": story.content_type,
        "assets": story.assets,
        "quality_scores": story.assets.get("quality_scores"),
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
