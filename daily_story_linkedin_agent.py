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


DEFAULT_HISTORY_PATH = Path("daily_story_history.json")
DEFAULT_OUTPUT_DIR = Path("daily_story_output")
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"
DEFAULT_OPENAI_IMAGE_SIZE = "1024x1024"
MIN_POST_WORDS = 35
MAX_POST_WORDS = 180

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

# Temporary file - content angles for splice into daily_story_linkedin_agent.py
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
    }
    return rng.choice(hooks_by_type.get(angle["content_type"], [angle["hook"]]))


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
    }
    if angle["content_type"] in before_after_by_type:
        return before_after_by_type[angle["content_type"]]
    sections = angle["sections"]
    return (
        "Before\n"
        f"{sections[0]}\n\n"
        "↓\n\n"
        "After\n"
        f"{sections[-1]}"
    )


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
    hook = choose_human_hook(rng, angle)
    before_after = build_before_after(angle)
    proof = before_after
    insight = build_insight(rng, angle, student_name=student_name)
    visual = build_curiosity_visual(angle)
    question = build_pillar_question(angle)
    return {
        "hook": hook,
        "proof": proof,
        "insight": insight,
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
        content_group=angle.get("content_group", "General"),
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
        "Create a square photorealistic LinkedIn image that tells a clear micro-story. "
        "Do not make a generic stock photo of a student holding a resume or laptop. "
        "The image must create curiosity through objects, evidence, and tension: "
        "rejected resumes, sticky notes, dashboards, scorecards, application counts, "
        "highlighted gaps, recruiter desk details, before/after profile screens, or "
        "assessment results. Topic: "
        f"{story.content_type}. "
        f"{story.hook} "
        f"Visual direction: {story.assets['visual']} "
        "Use a cinematic realistic style with natural lighting and shallow depth of "
        "field. People can appear, but the central story must be told by the desk, "
        "screen, papers, notes, or dashboard. Add subtle editorial overlays like "
        "circles, arrows, red/green stamps, or notification-style labels. Keep any "
        "text minimal, large, and readable. Do not include brand logos. The image "
        "should make someone pause and ask what happened before reading the post."
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
        "content_group": story.content_group,
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
        "content_group": story.content_group,
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
