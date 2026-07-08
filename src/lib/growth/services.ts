import type {
  Audience,
  CampaignAssetKind,
  CampaignAudience,
  ContentTypeId,
} from "../types";

export interface GrowthService {
  id: string;
  name: string;
  audience: CampaignAudience;
  blurb: string;
  goal: string;
  // Used to seed the educational LinkedIn post asset.
  contentTypeId: ContentTypeId;
  categoryId: string;
  postAudience: Audience;
  topic: string;
  // Plain-language offer used in outreach (employer services).
  offer?: string;
  proof?: string;
  assetKinds: CampaignAssetKind[];
}

const EMPLOYER_ASSETS: CampaignAssetKind[] = [
  "linkedin_post",
  "hr_email",
  "linkedin_message",
  "follow_up",
  "proposal",
];

const STUDENT_ASSETS: CampaignAssetKind[] = ["linkedin_post", "poll", "quiz"];

export const GROWTH_SERVICES: GrowthService[] = [
  // ---------- Employer services ----------
  {
    id: "hire_interns_10_days",
    name: "Hire Interns in 10 Days",
    audience: "employer",
    blurb: "Pre-assessed interns, shortlisted and ready within 10 days.",
    goal: "Get a hiring team to try a fast, pre-assessed intern pipeline.",
    contentTypeId: "hiring_tips",
    categoryId: "hire-interns",
    postAudience: "companies",
    topic: "How hiring teams can fill an intern role in 10 days",
    offer: "pre-assessed interns shortlisted for your role within 10 days",
    proof: "candidates are screened with a role-based assessment before you see them",
    assetKinds: EMPLOYER_ASSETS,
  },
  {
    id: "campus_hiring",
    name: "Campus Hiring",
    audience: "employer",
    blurb: "Run campus hiring without the logistics overhead.",
    goal: "Help a company run a lighter, faster campus hiring drive.",
    contentTypeId: "hiring_tips",
    categoryId: "campus-hiring",
    postAudience: "companies",
    topic: "A lighter way to run campus hiring this season",
    offer: "a managed campus hiring drive with pre-assessed shortlists",
    proof: "one assessment covers many colleges, so you compare like for like",
    assetKinds: EMPLOYER_ASSETS,
  },
  {
    id: "employer_branding",
    name: "Employer Branding",
    audience: "employer",
    blurb: "Become a company students actually want to intern at.",
    goal: "Help a company improve how students perceive its internships.",
    contentTypeId: "recruiter_tips",
    categoryId: "employer-branding",
    postAudience: "companies",
    topic: "What makes students choose one internship over another",
    offer: "help telling your internship story to the right students",
    proof: "students respond to clear scope and honest expectations, not perks",
    assetKinds: EMPLOYER_ASSETS,
  },
  {
    id: "assessment_platform",
    name: "Assessment Platform",
    audience: "employer",
    blurb: "Role-based assessments that predict on-the-job performance.",
    goal: "Get a hiring team to assess for the actual task, not a generic test.",
    contentTypeId: "hiring_tips",
    categoryId: "assessment",
    postAudience: "companies",
    topic: "Why role-based assessments beat generic aptitude tests",
    offer: "role-based assessments mapped to the task the intern will own",
    proof: "teams that assess for the task cut mis-hires early",
    assetKinds: EMPLOYER_ASSETS,
  },
  {
    id: "recruitment_automation",
    name: "Recruitment Automation",
    audience: "employer",
    blurb: "Automate screening so recruiters spend time on real conversations.",
    goal: "Help a recruiter remove the slow, repetitive parts of screening.",
    contentTypeId: "hiring_tips",
    categoryId: "recruitment-automation",
    postAudience: "companies",
    topic: "Automating the boring 80% of intern screening",
    offer: "automated first-round screening with a clear, auditable shortlist",
    proof: "recruiters get a ranked shortlist instead of 500 raw resumes",
    assetKinds: EMPLOYER_ASSETS,
  },

  // ---------- Student services ----------
  {
    id: "employability_score",
    name: "Employability Score",
    audience: "student",
    blurb: "A simple score that shows where a student stands.",
    goal: "Get students to check and act on their employability gaps.",
    contentTypeId: "student_tips",
    categoryId: "employability",
    postAudience: "students",
    topic: "What an employability score actually measures",
    assetKinds: STUDENT_ASSETS,
  },
  {
    id: "resume_review",
    name: "Resume Review",
    audience: "student",
    blurb: "Fix the resume mistakes recruiters notice first.",
    goal: "Get students to fix their resume's top third today.",
    contentTypeId: "resume_review",
    categoryId: "resume-review",
    postAudience: "students",
    topic: "The resume fix that takes 10 minutes and matters most",
    assetKinds: STUDENT_ASSETS,
  },
  {
    id: "ai_career",
    name: "AI Career",
    audience: "student",
    blurb: "Realistic ways to build an AI-era career.",
    goal: "Help students start one concrete AI-era skill.",
    contentTypeId: "ai_career",
    categoryId: "ai-careers",
    postAudience: "students",
    topic: "One AI-era skill worth starting this month",
    assetKinds: STUDENT_ASSETS,
  },
  {
    id: "interview_prep",
    name: "Interview Prep",
    audience: "student",
    blurb: "Practical interview technique with a worked example.",
    goal: "Help students structure stronger interview answers.",
    contentTypeId: "student_tips",
    categoryId: "interview-tips",
    postAudience: "students",
    topic: "How to answer an interview question you were not ready for",
    assetKinds: STUDENT_ASSETS,
  },
  {
    id: "internship_verification",
    name: "Internship Verification",
    audience: "student",
    blurb: "Check an internship is real before applying.",
    goal: "Help students avoid fake or exploitative internships.",
    contentTypeId: "linkedin_post",
    categoryId: "internship-verification",
    postAudience: "students",
    topic: "How to verify an internship before you apply",
    assetKinds: STUDENT_ASSETS,
  },
  {
    id: "skill_gap_analysis",
    name: "Skill Gap Analysis",
    audience: "student",
    blurb: "See the gap between your projects and real work.",
    goal: "Help students find and close one skill gap.",
    contentTypeId: "ai_career",
    categoryId: "skill-gap",
    postAudience: "students",
    topic: "Finding the one skill gap holding your applications back",
    assetKinds: STUDENT_ASSETS,
  },

  // ---------- Community ----------
  {
    id: "polls",
    name: "Poll",
    audience: "community",
    blurb: "A quick poll that starts a useful conversation.",
    goal: "Spark engagement and learn what the audience thinks.",
    contentTypeId: "linkedin_post",
    categoryId: "poll",
    postAudience: "community",
    topic: "How do you approach your job search",
    assetKinds: ["poll"],
  },
  {
    id: "weekly_quiz",
    name: "Weekly Quiz",
    audience: "community",
    blurb: "A short quiz that teaches while it tests.",
    goal: "Teach one useful thing through a quick quiz.",
    contentTypeId: "linkedin_post",
    categoryId: "weekly-quiz",
    postAudience: "community",
    topic: "Resume and interview basics",
    assetKinds: ["quiz"],
  },
  {
    id: "student_spotlight",
    name: "Student Spotlight",
    audience: "community",
    blurb: "Celebrate a real student's progress (template to fill).",
    goal: "Recognise a real student without inventing a story.",
    contentTypeId: "linkedin_post",
    categoryId: "student-spotlight",
    postAudience: "community",
    topic: "Student spotlight",
    assetKinds: ["student_spotlight"],
  },
  {
    id: "company_spotlight",
    name: "Company Spotlight",
    audience: "community",
    blurb: "Feature a company doing internships well (template to fill).",
    goal: "Recognise a real company partner without hype.",
    contentTypeId: "linkedin_post",
    categoryId: "company-spotlight",
    postAudience: "community",
    topic: "Company spotlight",
    assetKinds: ["company_spotlight"],
  },
  {
    id: "recruiter_insights",
    name: "Recruiter Insights",
    audience: "community",
    blurb: "A recruiter-side insight that helps students.",
    goal: "Share what recruiters notice, framed to help.",
    contentTypeId: "recruiter_tips",
    categoryId: "recruiter-tips",
    postAudience: "students",
    topic: "One thing recruiters notice that students miss",
    assetKinds: ["recruiter_insight", "poll"],
  },
];

export function getService(id: string): GrowthService | undefined {
  return GROWTH_SERVICES.find((s) => s.id === id);
}

export function servicesByAudience(audience: CampaignAudience): GrowthService[] {
  return GROWTH_SERVICES.filter((s) => s.audience === audience);
}
