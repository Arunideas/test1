import type {
  BrandStyle,
  Category,
  Database,
  ImageTemplate,
  PromptTemplate,
  Topic,
} from "./types";

function slug(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

interface CatDef {
  pillar: Category["pillar"];
  audience: Category["audience"];
  names: string[];
}

const CATEGORY_DEFS: CatDef[] = [
  {
    pillar: "Students",
    audience: "students",
    names: [
      "Employability",
      "Resume Review",
      "Interview Tips",
      "Skill Gap",
      "Projects",
      "AI Tools",
      "AI Careers",
      "AI Learning",
      "Career Roadmap",
      "Portfolio",
      "Student Success",
      "Internship Verification",
      "Internship Opportunities",
      "Resume Mistakes",
      "Interview Questions",
      "Communication Skills",
      "Coding",
      "Soft Skills",
      "Productivity",
      "Career Planning",
    ],
  },
  {
    pillar: "Companies",
    audience: "companies",
    names: [
      "Hire Interns",
      "Campus Hiring",
      "Recruiter Tips",
      "Employer Branding",
      "Intern Hiring",
      "Hiring Trends",
      "Assessment",
      "Recruitment Automation",
      "HR Insights",
      "Hiring Challenges",
    ],
  },
  {
    pillar: "Market",
    audience: "market",
    names: [
      "Industry Trends",
      "Salary Reports",
      "AI Market",
      "Technology",
      "Future Skills",
      "Research",
      "College Rankings",
      "Employability Reports",
    ],
  },
  {
    pillar: "Community",
    audience: "community",
    names: [
      "Events",
      "Challenges",
      "Weekly Quiz",
      "Poll",
      "Student Spotlight",
      "Company Spotlight",
      "Weekly Summary",
      "Announcements",
    ],
  },
];

export function buildCategories(): Category[] {
  const out: Category[] = [];
  for (const def of CATEGORY_DEFS) {
    for (const name of def.names) {
      out.push({
        id: slug(name),
        name,
        pillar: def.pillar,
        audience: def.audience,
      });
    }
  }
  return out;
}

const BRAND_STYLE: BrandStyle = {
  id: "woi-brand",
  brandName: "World of Interns",
  positioningPrimary: "Helping students become employable in the AI era.",
  positioningSecondary:
    "Helping companies hire pre-assessed interns within 10 days.",
  tone: ["Practical", "Honest", "Helpful", "Evidence driven", "Calm", "Friendly"],
  avoidTone: [
    "Emotional",
    "Inspirational",
    "Fake storytelling",
    "Sales language",
    "Clickbait",
  ],
  maxLinesPerParagraph: 3,
  bannedPhrases: [
    "register now",
    "sign up now",
    "buy now",
    "limited offer",
    "don't miss",
    "act now",
    "game changer",
    "game-changer",
    "revolutionary",
    "unlock your potential",
    "unleash",
    "supercharge",
    "10x your",
    "crush it",
    "the secret to",
    "you won't believe",
    "mind-blowing",
    "life-changing",
    "dream job",
    "hustle",
    "grind",
    "manifest",
    "in today's fast-paced world",
    "as an ai",
    "leverage synergies",
    "circle back",
    "move the needle",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "next-level",
  ],
  bannedNames: ["john", "rahul", "dev", "priya", "raj", "amit", "neha", "sam"],
  allowedCtas: [
    "What do you think?",
    "Would you apply?",
    "Which skill are you learning right now?",
    "What would you add?",
    "Which of these have you tried?",
    "How do you handle this?",
    "What has worked for you?",
  ],
  structure: ["Hook", "Problem", "Evidence", "Solution", "Action", "Question"],
  signature: "— World of Interns",
  promoRatioTarget: 0.05,
  hashtagPool: [
    "#Internships",
    "#Employability",
    "#Careers",
    "#AICareers",
    "#Hiring",
    "#CampusHiring",
    "#ResumeTips",
    "#StudentCareers",
    "#FutureSkills",
    "#WorldOfInterns",
  ],
};

const IMAGE_TEMPLATES: ImageTemplate[] = [
  {
    id: "statistics",
    name: "Statistics Card",
    layout: "statistics",
    description: "A clean stat highlighted on a desk photo.",
    scene:
      "a real wooden student desk with an open notebook, a pen and a laptop, shot on a smartphone, natural window light, Indian hostel room",
  },
  {
    id: "checklist",
    name: "Checklist",
    layout: "checklist",
    description: "A short actionable checklist on a notebook.",
    scene:
      "a spiral notebook with a hand-written checklist, cup of chai beside it, natural daylight, documentary style",
  },
  {
    id: "before_after",
    name: "Before / After",
    layout: "before_after",
    description: "Split screen comparing a weak vs improved resume.",
    scene:
      "two printed resume pages side by side on a desk, one marked with a red pen, realistic smartphone photo",
  },
  {
    id: "question_card",
    name: "Question Card",
    layout: "question_card",
    description: "A single question over a plain workspace.",
    scene:
      "a laptop on a plain desk in an Indian college library, soft natural light, no people",
  },
  {
    id: "top_list",
    name: "Top List",
    layout: "top_list",
    description: "A ranked list of items on a whiteboard.",
    scene:
      "a whiteboard with a hand-written numbered list in a classroom, marker on the tray, daylight",
  },
  {
    id: "timeline",
    name: "Timeline / Roadmap",
    layout: "timeline",
    description: "A simple step-by-step roadmap.",
    scene:
      "a notebook page with a hand-drawn arrow roadmap, pen resting on it, warm desk lamp light",
  },
  {
    id: "comparison",
    name: "Skill Comparison",
    layout: "comparison",
    description: "Two columns comparing skills or options.",
    scene:
      "a whiteboard split into two columns with hand-written notes, office meeting room, natural light",
  },
  {
    id: "quote",
    name: "Insight Quote",
    layout: "quote",
    description: "A short insight rendered as plain text on paper.",
    scene:
      "a plain sticky note on a laptop lid, minimal desk, natural light, documentary photo",
  },
];

const PROMPTS: PromptTemplate[] = [
  {
    id: "resume_review",
    name: "Resume Review Prompt",
    contentTypeId: "resume_review",
    imageTemplateId: "before_after",
    description: "Reviews a common resume mistake and how to fix it.",
    systemPrompt:
      "Explain one specific, common resume mistake Indian students make and the exact fix. Use evidence from what recruiters actually scan for. No fluff.",
  },
  {
    id: "ai_tool_of_the_week",
    name: "AI Tool Prompt",
    contentTypeId: "ai_tool_of_the_week",
    imageTemplateId: "checklist",
    description: "Introduces one AI tool and a concrete way a student can use it.",
    systemPrompt:
      "Introduce one AI tool. Explain a single practical task a final year student can finish with it today. Include one limitation. No hype.",
  },
  {
    id: "interview_tips",
    name: "Interview Prompt",
    contentTypeId: "student_tips",
    imageTemplateId: "question_card",
    description: "One interview technique with a worked example.",
    systemPrompt:
      "Give one interview technique. Show a short before/after of a weak vs strong answer. Keep it practical.",
  },
  {
    id: "company_hiring",
    name: "Company Hiring Prompt",
    contentTypeId: "hiring_tips",
    imageTemplateId: "statistics",
    description: "Helps a hiring team make internships work.",
    systemPrompt:
      "Give a hiring team one concrete way to run internships better. Use a realistic hiring insight. Avoid selling.",
  },
  {
    id: "internship_alert",
    name: "Internship Alert Prompt",
    contentTypeId: "linkedin_post",
    imageTemplateId: "top_list",
    description: "Shares what to check before applying to an internship.",
    systemPrompt:
      "Explain how a student should verify an internship before applying. Focus on trust signals and red flags.",
  },
  {
    id: "future_skill",
    name: "Future Skill Prompt",
    contentTypeId: "ai_career",
    imageTemplateId: "timeline",
    description: "Explains a skill worth learning for the AI era.",
    systemPrompt:
      "Explain one future-facing skill and a realistic 4-week way to start. No predictions, only what to do now.",
  },
  {
    id: "recruiter_tip",
    name: "Recruiter Tip Prompt",
    contentTypeId: "recruiter_tips",
    imageTemplateId: "comparison",
    description: "A recruiter-side insight that also helps students.",
    systemPrompt:
      "Share one thing recruiters notice that students miss. Frame it from the recruiter's desk. Stay neutral.",
  },
  {
    id: "student_story",
    name: "Student Insight Prompt",
    contentTypeId: "student_tips",
    imageTemplateId: "quote",
    description: "A platform insight framed without fake stories.",
    systemPrompt:
      "Share a pattern seen across many students (no invented names). Turn it into one action. Keep it honest.",
  },
];

const TOPIC_SEEDS: Array<{
  topic: string;
  categoryId: string;
  subcategory?: string;
  difficulty: Topic["difficulty"];
  priority: number;
  keywords: string[];
  source: string;
}> = [
  {
    topic: "The one resume line recruiters read first",
    categoryId: "resume-review",
    subcategory: "Formatting",
    difficulty: "beginner",
    priority: 5,
    keywords: ["resume", "recruiter", "summary"],
    source: "platform-insight",
  },
  {
    topic: "How to verify an internship before you apply",
    categoryId: "internship-verification",
    difficulty: "beginner",
    priority: 5,
    keywords: ["scam", "trust", "verify", "internship"],
    source: "platform-insight",
  },
  {
    topic: "Using an AI tool to tailor your resume in 10 minutes",
    categoryId: "ai-tools",
    difficulty: "intermediate",
    priority: 4,
    keywords: ["ai", "resume", "tool"],
    source: "trend",
  },
  {
    topic: "The skill gap between college projects and real work",
    categoryId: "skill-gap",
    difficulty: "intermediate",
    priority: 4,
    keywords: ["skills", "projects", "gap"],
    source: "research",
  },
  {
    topic: "Why your STAR interview answers fall flat",
    categoryId: "interview-tips",
    difficulty: "intermediate",
    priority: 4,
    keywords: ["interview", "star", "answers"],
    source: "platform-insight",
  },
  {
    topic: "A realistic 4-week roadmap to learn data skills",
    categoryId: "ai-learning",
    difficulty: "beginner",
    priority: 3,
    keywords: ["roadmap", "learning", "data"],
    source: "platform-insight",
  },
  {
    topic: "How hiring teams can run a 10-day internship pipeline",
    categoryId: "hire-interns",
    difficulty: "advanced",
    priority: 4,
    keywords: ["hiring", "pipeline", "internship"],
    source: "platform-insight",
  },
  {
    topic: "What recruiters actually notice in the first 7 seconds",
    categoryId: "recruiter-tips",
    difficulty: "beginner",
    priority: 4,
    keywords: ["recruiter", "screening", "resume"],
    source: "platform-insight",
  },
  {
    topic: "Building a portfolio when you have no work experience",
    categoryId: "portfolio",
    difficulty: "beginner",
    priority: 3,
    keywords: ["portfolio", "projects", "beginner"],
    source: "platform-insight",
  },
  {
    topic: "The future skill most students are ignoring",
    categoryId: "future-skills",
    difficulty: "intermediate",
    priority: 3,
    keywords: ["future", "skills", "ai"],
    source: "trend",
  },
];

export function buildTopics(categories: Category[]): Topic[] {
  const valid = new Set(categories.map((c) => c.id));
  const now = new Date();
  return TOPIC_SEEDS.filter((t) => valid.has(t.categoryId)).map((t, i) => ({
    id: `topic-${i + 1}`,
    topic: t.topic,
    categoryId: t.categoryId,
    subcategory: t.subcategory,
    difficulty: t.difficulty,
    priority: t.priority,
    status: "idea" as const,
    lastGeneratedAt: null,
    lastPublishedAt: null,
    performanceScore: 50,
    duplicateScore: 0,
    popularity: 40 + ((i * 7) % 40),
    trendScore: 30 + ((i * 11) % 50),
    source: t.source,
    keywords: t.keywords,
    // stagger created time via topic id ordering
    ...(now ? {} : {}),
  }));
}

export function buildSeedDatabase(): Database {
  const categories = buildCategories();
  return {
    categories,
    topics: buildTopics(categories),
    brandStyle: BRAND_STYLE,
    prompts: PROMPTS,
    imageTemplates: IMAGE_TEMPLATES,
    images: [],
    posts: [],
  };
}
