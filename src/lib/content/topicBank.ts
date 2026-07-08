// A curated bank of concrete, non-duplicate topics per category.
// Large enough that a 90-day calendar (each weekday slot recurs ~13 times,
// rotating across a few categories) can be filled without repeating a topic.

export interface BankEntry {
  categoryId: string;
  topics: string[];
  tags: string[];
}

export const TOPIC_BANK: BankEntry[] = [
  // ---- Monday: AI Tool ----
  {
    categoryId: "ai-tools",
    tags: ["ai", "tools", "productivity"],
    topics: [
      "Using AI to turn a rough resume draft into clean bullet points",
      "An AI tool that mock-interviews you for free",
      "How to fact-check anything an AI writing tool gives you",
      "Turning lecture notes into flashcards with one AI prompt",
      "Using AI to rewrite a cold email without sounding robotic",
      "A safe way to use AI for coding assignments",
      "Cleaning up messy data with an AI spreadsheet assistant",
      "Using AI to summarise a 40-page report before an interview",
    ],
  },
  {
    categoryId: "productivity",
    tags: ["productivity", "habits", "focus"],
    topics: [
      "A two-list system for job applications that actually holds",
      "Time-boxing your prep when you have exams and applications",
      "The one weekly review that keeps a job search on track",
      "How to batch your applications instead of doing them daily",
      "Cutting your tool stack down to three apps for a job search",
    ],
  },
  {
    categoryId: "ai-learning",
    tags: ["ai", "learning", "study"],
    topics: [
      "Learning to prompt well without a paid course",
      "A weekend project to understand how models actually work",
      "How to learn AI basics when you are not from CS",
      "Reading an AI paper without a research background",
    ],
  },

  // ---- Tuesday: Resume Review ----
  {
    categoryId: "resume-review",
    tags: ["resume", "recruiter", "formatting"],
    topics: [
      "The one resume line recruiters read first",
      "Why your resume summary is costing you interviews",
      "Ordering resume sections for a fresher with no experience",
      "How to show a project on your resume so it gets noticed",
      "Fixing a one-page vs two-page resume for Indian students",
      "Writing a resume bullet that survives a 7-second scan",
      "How to list skills without a wall of keywords",
    ],
  },
  {
    categoryId: "resume-mistakes",
    tags: ["resume", "mistakes"],
    topics: [
      "The photo-and-objective habit that weakens most resumes",
      "Why 'responsible for' quietly kills your bullets",
      "The formatting mistake that breaks resume parsers",
      "Listing every course instead of your three best projects",
      "Using ratings out of 5 for your skills, and what to do instead",
      "Copying a template that hides your actual work",
    ],
  },

  // ---- Wednesday: Internship Jobs ----
  {
    categoryId: "internship-opportunities",
    tags: ["internship", "applications", "jobs"],
    topics: [
      "How to find internships that are not on the big job boards",
      "What a good internship description should actually tell you",
      "Applying to fewer internships but with tailored notes",
      "How to read a stipend range before you apply",
      "Remote vs in-office internships for a first role",
      "When a 'free' internship is worth it and when it is not",
      "How to shortlist internships without wasting a week",
      "Applying early vs applying polished, and which wins",
    ],
  },
  {
    categoryId: "internship-verification",
    tags: ["internship", "trust", "scam"],
    topics: [
      "How to verify an internship before you apply",
      "Five red flags of a fake internship listing",
      "Checking a company's LinkedIn presence before applying",
      "Why an internship asking for a deposit is a scam",
      "How to read Glassdoor reviews without overreacting",
      "Spotting a copy-paste recruiter message",
      "Confirming a stipend offer is real before you commit",
    ],
  },

  // ---- Thursday: Recruiter Insight ----
  {
    categoryId: "recruiter-tips",
    tags: ["recruiter", "screening", "hiring"],
    topics: [
      "What recruiters actually notice in the first 7 seconds",
      "The gap between what students send and what recruiters scan",
      "Why recruiters skip long summaries",
      "How a clear job title on your profile helps recruiters find you",
      "What a recruiter thinks when your projects have no results",
      "The follow-up message that recruiters do not mind",
    ],
  },
  {
    categoryId: "hr-insights",
    tags: ["hr", "hiring", "process"],
    topics: [
      "Why hiring feels slow from the HR side",
      "How HR teams shortlist when they get 500 applications",
      "What an assessment score really tells a hiring team",
      "The quiet reason good candidates get rejected",
    ],
  },
  {
    categoryId: "hiring-trends",
    tags: ["hiring", "trends", "market"],
    topics: [
      "Why pre-assessed hiring is replacing long interview loops",
      "The shift from degrees to demonstrated skills",
      "What role-based assessments changed about intern hiring",
      "Why companies are hiring interns faster than before",
    ],
  },

  // ---- Friday: Future Skill ----
  {
    categoryId: "future-skills",
    tags: ["future", "skills", "ai-era"],
    topics: [
      "The future skill most students are ignoring",
      "Why writing clearly is becoming a technical skill",
      "Data literacy for people who are scared of maths",
      "Learning to work alongside AI instead of against it",
      "Why debugging your own thinking beats memorising",
    ],
  },
  {
    categoryId: "ai-careers",
    tags: ["ai", "careers"],
    topics: [
      "What an entry-level AI-adjacent job actually looks like",
      "How non-CS students break into AI-heavy roles",
      "The portfolio that gets you a first AI-related internship",
      "Why prompt skills alone are not a career",
    ],
  },
  {
    categoryId: "skill-gap",
    tags: ["skills", "gap", "projects"],
    topics: [
      "The skill gap between college projects and real work",
      "Why your project works on your laptop but not in an interview",
      "Closing the gap between theory marks and practical skill",
      "The soft-skill gap no syllabus covers",
    ],
  },

  // ---- Saturday: Student Story / Tips ----
  {
    categoryId: "student-success",
    tags: ["students", "patterns", "success"],
    topics: [
      "A pattern we see in students who get callbacks",
      "What changed for students who stopped mass-applying",
      "The habit behind students who clear assessments",
      "How students with average marks still get hired",
    ],
  },
  {
    categoryId: "interview-tips",
    tags: ["interview", "prep"],
    topics: [
      "Why your STAR interview answers fall flat",
      "How to answer 'tell me about yourself' without rambling",
      "Handling a question when you do not know the answer",
      "The one-minute rule for interview answers",
      "How to talk about a project you built with a team",
    ],
  },
  {
    categoryId: "communication-skills",
    tags: ["communication", "soft-skills"],
    topics: [
      "Writing a follow-up email that does not sound needy",
      "How to explain a technical project to a non-technical person",
      "Saying 'I don't know' in a way that still builds trust",
    ],
  },
  {
    categoryId: "soft-skills",
    tags: ["soft-skills", "work"],
    topics: [
      "Why reliability beats brilliance in your first internship",
      "Asking good questions on your first week at work",
      "Taking feedback without getting defensive",
    ],
  },

  // ---- Sunday: Weekly Report / Market ----
  {
    categoryId: "employability-reports",
    tags: ["report", "employability", "data"],
    topics: [
      "What our weekly employability data says about skill gaps",
      "The three skills showing up most in intern assessments",
      "A weekly read on which roles students are applying to",
      "Which resume changes moved the callback rate this week",
      "What assessment scores tell us about job-readiness",
    ],
  },
  {
    categoryId: "industry-trends",
    tags: ["industry", "trends"],
    topics: [
      "Where entry-level hiring is heading this quarter",
      "The industries hiring the most interns right now",
      "Why smaller companies are a better first internship",
      "What changed in fresher hiring over the last year",
    ],
  },
  {
    categoryId: "salary-reports",
    tags: ["salary", "stipend", "data"],
    topics: [
      "What a realistic intern stipend looks like by role",
      "Why stipend is not the only number that matters",
      "How to compare two internship offers fairly",
      "Stipend vs learning: how to weigh a first offer",
    ],
  },
  {
    categoryId: "research",
    tags: ["research", "reports"],
    topics: [
      "What the latest employability research misses about freshers",
      "Reading a hiring report without falling for the headline",
      "What the data says about projects vs marks",
      "A closer look at why callbacks stall for freshers",
    ],
  },
];
