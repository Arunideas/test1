// Shared domain types for the World of Interns Content Intelligence Platform.

export type Audience = "students" | "companies" | "market" | "community";

export type ContentTypeId =
  | "linkedin_post"
  | "ai_tool_of_the_week"
  | "resume_review"
  | "recruiter_tips"
  | "ai_career"
  | "student_tips"
  | "hiring_tips";

export interface Category {
  id: string;
  name: string;
  pillar: "Students" | "Companies" | "Market" | "Community";
  audience: Audience;
}

export type Difficulty = "beginner" | "intermediate" | "advanced";
export type TopicStatus = "idea" | "queued" | "generated" | "published";

export interface Topic {
  id: string;
  topic: string;
  categoryId: string;
  subcategory?: string;
  difficulty: Difficulty;
  priority: number; // 1 (low) - 5 (high)
  status: TopicStatus;
  lastGeneratedAt?: string | null;
  lastPublishedAt?: string | null;
  performanceScore: number; // 0-100
  duplicateScore: number; // 0-100 (higher = more likely duplicate)
  popularity: number; // 0-100
  trendScore: number; // 0-100
  source: string;
  keywords: string[];
}

export interface BrandStyle {
  id: string;
  brandName: string;
  positioningPrimary: string;
  positioningSecondary: string;
  tone: string[];
  avoidTone: string[];
  maxLinesPerParagraph: number;
  bannedPhrases: string[];
  bannedNames: string[];
  allowedCtas: string[];
  structure: string[]; // Hook -> Problem -> ...
  signature: string;
  promoRatioTarget: number; // max fraction of promotional content (e.g. 0.05)
  hashtagPool: string[];
}

export interface PromptTemplate {
  id: string;
  name: string;
  contentTypeId: ContentTypeId;
  description: string;
  systemPrompt: string;
  imageTemplateId: string;
}

export interface ImageTemplate {
  id: string;
  name: string;
  description: string;
  layout:
    | "statistics"
    | "checklist"
    | "before_after"
    | "question_card"
    | "quote"
    | "top_list"
    | "timeline"
    | "comparison";
  scene: string; // documentary scene description used for the AI image prompt
}

export interface GeneratedImage {
  id: string;
  templateId: string;
  layout: ImageTemplate["layout"];
  prompt: string; // AI image-generation prompt (documentary style)
  svg: string; // locally rendered authentic composition (data-independent of any API)
  altText: string;
  source: "local-svg" | "openai";
  createdAt: string;
}

export interface QualityScores {
  educational: number;
  trust: number;
  actionable: number;
  authentic: number;
  human: number;
  promotional: number; // lower is better
  overall: number;
}

export interface PostVersion {
  version: number;
  body: string;
  imageId?: string | null;
  createdAt: string;
  note: string;
}

export interface GeneratedPost {
  id: string;
  title: string;
  contentTypeId: ContentTypeId;
  categoryId: string;
  topicId?: string | null;
  topic: string;
  audience: Audience;
  body: string;
  hook: string;
  cta: string;
  hashtags: string[];
  imagePrompt: string;
  imageId?: string | null;
  scores: QualityScores;
  warnings: string[];
  wordCount: number;
  readTimeSeconds: number;
  engine: "rule-based" | "openai";
  status: "draft" | "ready" | "published";
  versions: PostVersion[];
  createdAt: string;
  updatedAt: string;
}

export interface Database {
  categories: Category[];
  topics: Topic[];
  brandStyle: BrandStyle;
  prompts: PromptTemplate[];
  imageTemplates: ImageTemplate[];
  images: GeneratedImage[];
  posts: GeneratedPost[];
}

export interface GenerateRequest {
  contentTypeId: ContentTypeId;
  topicId?: string;
  topic?: string;
  categoryId?: string;
  audience?: Audience;
  extraContext?: string;
}
