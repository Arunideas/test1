import type { QuizQuestion } from "../types";
import type { GrowthService } from "./services";

export interface CommunityAsset {
  title: string;
  body: string;
  hashtags?: string[];
  meta?: { pollOptions?: string[]; quiz?: QuizQuestion[]; placeholders?: string[] };
}

interface PollDef {
  question: string;
  options: string[];
}

const POLLS: Record<string, PollDef> = {
  polls: {
    question: "What slows your job search down the most?",
    options: ["Writing the resume", "Finding real openings", "Interviews", "Hearing back"],
  },
  recruiter_insights: {
    question: "What do you think recruiters notice first on a resume?",
    options: ["Your college", "Your projects", "Your skills list", "Your formatting"],
  },
  resume_review: {
    question: "How many versions of your resume do you keep?",
    options: ["Just one", "Two or three", "One per role", "I lose count"],
  },
  interview_prep: {
    question: "What is the hardest part of an interview for you?",
    options: ["First impression", "Technical questions", "Blanking out", "Salary talk"],
  },
};

export function poll(service: GrowthService): CommunityAsset {
  const def = POLLS[service.id] ?? POLLS.polls;
  const body = [
    def.question,
    "",
    "No wrong answer — genuinely curious what most people pick.",
    "",
    "Vote below, and drop a comment if your reason is not on the list.",
  ].join("\n");
  return {
    title: "Poll",
    body,
    meta: { pollOptions: def.options },
    hashtags: ["#Poll", "#Careers", "#WorldOfInterns"],
  };
}

const QUIZZES: Record<string, QuizQuestion[]> = {
  weekly_quiz: [
    {
      question: "How long does a recruiter usually spend on a first resume scan?",
      options: ["About 7 seconds", "About 2 minutes", "About 10 minutes", "It varies a lot"],
      answerIndex: 0,
    },
    {
      question: "Which resume line matters most?",
      options: [
        "Your career objective",
        "Your hobbies",
        "Your top result with a number",
        "Your photo",
      ],
      answerIndex: 2,
    },
    {
      question: "Before applying to an internship, you should first:",
      options: [
        "Pay the registration fee",
        "Verify the company is real",
        "Send your Aadhaar",
        "Accept immediately",
      ],
      answerIndex: 1,
    },
  ],
};

export function quiz(service: GrowthService): CommunityAsset {
  const questions = QUIZZES[service.id] ?? QUIZZES.weekly_quiz;
  const lines: string[] = ["Weekly quiz. Three quick questions. Answers at the end.", ""];
  questions.forEach((q, i) => {
    lines.push(`Q${i + 1}. ${q.question}`);
    q.options.forEach((o, oi) => lines.push(`  ${String.fromCharCode(65 + oi)}. ${o}`));
    lines.push("");
  });
  lines.push("Answers:");
  questions.forEach((q, i) => {
    lines.push(`Q${i + 1}: ${String.fromCharCode(65 + q.answerIndex)}`);
  });
  lines.push("");
  lines.push("How many did you get? Comment your score.");
  return {
    title: "Weekly quiz",
    body: lines.join("\n"),
    meta: { quiz: questions },
    hashtags: ["#WeeklyQuiz", "#Careers", "#WorldOfInterns"],
  };
}

export function studentSpotlight(): CommunityAsset {
  const body = [
    "Student spotlight.",
    "",
    "[Student name], [Year] year at [College].",
    "",
    "What they did: [one concrete thing — a project, a skill, an internship].",
    "What changed: [the result, in one line — a callback, an offer, a working project].",
    "",
    "In their words: “[one honest sentence from the student].”",
    "",
    "Nice work, [Student name]. What are you learning next?",
  ].join("\n");
  return {
    title: "Student spotlight (fill the placeholders with real details)",
    body,
    meta: { placeholders: ["Student name", "Year", "College"] },
    hashtags: ["#StudentSpotlight", "#WorldOfInterns"],
  };
}

export function companySpotlight(): CommunityAsset {
  const body = [
    "Company spotlight.",
    "",
    "[Company] runs internships worth the intern's time.",
    "",
    "What they do well: [one specific thing — clear scope, real mentorship, honest expectations].",
    "Roles they hire: [role 1], [role 2].",
    "",
    "Why it matters: interns learn fastest when the work is real and the scope is clear.",
    "",
    "If your team does internships like this, we would like to feature you too.",
  ].join("\n");
  return {
    title: "Company spotlight (fill the placeholders with real details)",
    body,
    meta: { placeholders: ["Company", "role 1", "role 2"] },
    hashtags: ["#CompanySpotlight", "#Hiring", "#WorldOfInterns"],
  };
}
