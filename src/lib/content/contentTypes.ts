import type { Audience, ContentTypeId } from "../types";

export interface ContentTypeDef {
  id: ContentTypeId;
  name: string;
  defaultAudience: Audience;
  defaultImageTemplateId: string;
  blurb: string;
  suggestedCategoryIds: string[];
}

export const CONTENT_TYPES: ContentTypeDef[] = [
  {
    id: "linkedin_post",
    name: "LinkedIn Post",
    defaultAudience: "students",
    defaultImageTemplateId: "top_list",
    blurb: "A general educational LinkedIn post.",
    suggestedCategoryIds: ["employability", "internship-opportunities", "career-roadmap"],
  },
  {
    id: "ai_tool_of_the_week",
    name: "AI Tool of the Week",
    defaultAudience: "students",
    defaultImageTemplateId: "checklist",
    blurb: "One AI tool and a concrete way to use it today.",
    suggestedCategoryIds: ["ai-tools", "ai-learning", "productivity"],
  },
  {
    id: "resume_review",
    name: "Resume Review",
    defaultAudience: "students",
    defaultImageTemplateId: "before_after",
    blurb: "A common resume mistake and the exact fix.",
    suggestedCategoryIds: ["resume-review", "resume-mistakes"],
  },
  {
    id: "recruiter_tips",
    name: "Recruiter Tips",
    defaultAudience: "companies",
    defaultImageTemplateId: "comparison",
    blurb: "What recruiters notice, framed to help students too.",
    suggestedCategoryIds: ["recruiter-tips", "hr-insights", "assessment"],
  },
  {
    id: "ai_career",
    name: "AI Career",
    defaultAudience: "students",
    defaultImageTemplateId: "timeline",
    blurb: "A future-facing skill and a realistic way to start.",
    suggestedCategoryIds: ["ai-careers", "future-skills", "ai-learning"],
  },
  {
    id: "student_tips",
    name: "Student Tips",
    defaultAudience: "students",
    defaultImageTemplateId: "question_card",
    blurb: "One practical thing a student can act on today.",
    suggestedCategoryIds: ["interview-tips", "communication-skills", "soft-skills"],
  },
  {
    id: "hiring_tips",
    name: "Hiring Tips",
    defaultAudience: "companies",
    defaultImageTemplateId: "statistics",
    blurb: "A concrete way for hiring teams to run internships better.",
    suggestedCategoryIds: ["hire-interns", "campus-hiring", "intern-hiring"],
  },
];

export function getContentType(id: ContentTypeId): ContentTypeDef {
  const found = CONTENT_TYPES.find((c) => c.id === id);
  if (!found) throw new Error(`Unknown content type: ${id}`);
  return found;
}
