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
  tags: string[];
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

export type CalendarStatus =
  | "planned"
  | "approved"
  | "rejected"
  | "generated"
  | "published"
  | "skipped";

export interface CalendarEntry {
  id: string;
  date: string; // YYYY-MM-DD
  slot: string; // weekday theme label, e.g. "AI Tool"
  contentTypeId: ContentTypeId;
  categoryId: string;
  topicId: string;
  topicText: string;
  audience: Audience;
  status: CalendarStatus;
  duplicateScore: number; // 0-1 similarity to nearest scheduled/published topic
  topicScore: number; // 0-100 ranking score used when scheduled
  postId?: string | null;
  approvedBy?: string | null;
  approvedAt?: string | null;
  note?: string;
  createdAt: string;
}

export interface PerformanceRecord {
  id: string;
  calendarEntryId?: string | null;
  postId?: string | null;
  topicId: string;
  categoryId: string;
  date: string;
  metrics: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
    impressions: number;
    ctr: number; // 0-1
    engagementRate: number; // 0-1
  };
  score: number; // 0-100 blended performance score
  createdAt: string;
}

export interface PlatformConfig {
  rotationWindowDays: number; // avoid repeating a topic within this window (default 45)
  postsPerDay: number;
  duplicateThreshold: number; // 0-1 similarity above which a topic is a duplicate
  weekdayPlan: WeekdaySlot[]; // 7 entries, Sunday..Saturday
}

export interface WeekdaySlot {
  weekday: number; // 0 = Sunday ... 6 = Saturday
  label: string; // "AI Tool", "Resume Review", ...
  contentTypeId: ContentTypeId;
  categoryIds: string[]; // rotate across these categories
}

export type CampaignAudience = "employer" | "student" | "community";

export type CampaignAssetKind =
  | "linkedin_post"
  | "hr_email"
  | "linkedin_message"
  | "follow_up"
  | "proposal"
  | "poll"
  | "quiz"
  | "student_spotlight"
  | "company_spotlight"
  | "recruiter_insight";

export interface QuizQuestion {
  question: string;
  options: string[];
  answerIndex: number;
}

export interface CampaignAsset {
  id: string;
  kind: CampaignAssetKind;
  title: string;
  subject?: string; // for emails
  body: string;
  hashtags?: string[];
  meta?: {
    pollOptions?: string[];
    quiz?: QuizQuestion[];
    placeholders?: string[]; // e.g. ["First name", "Company"]
  };
  scores?: QualityScores;
  warnings?: string[];
  engine: "rule-based" | "openai";
}

export interface Campaign {
  id: string;
  name: string;
  audience: CampaignAudience;
  serviceId: string;
  serviceName: string;
  goal: string;
  assets: CampaignAsset[];
  createdAt: string;
  status: "draft" | "ready";
}

export type PublishMode = "immediate" | "scheduled" | "draft" | "approval";

export type PublishStatus =
  | "draft"
  | "pending_approval"
  | "scheduled"
  | "queued"
  | "publishing"
  | "published"
  | "failed"
  | "cancelled";

export interface PublishJob {
  id: string;
  postId?: string | null;
  calendarEntryId?: string | null;
  target: "linkedin";
  mode: PublishMode;
  status: PublishStatus;
  text: string;
  hashtags: string[];
  imageId?: string | null;
  visibility: "PUBLIC" | "CONNECTIONS";
  scheduledAt?: string | null;
  attempts: number;
  maxAttempts: number;
  nextAttemptAt?: string | null;
  lastError?: string | null;
  postUrl?: string | null;
  simulated: boolean;
  createdAt: string;
  updatedAt: string;
  approvedAt?: string | null;
  publishedAt?: string | null;
  log: PublishLogLine[];
}

export interface PublishLogLine {
  at: string;
  message: string;
  level: "info" | "error" | "success";
}

export interface Database {
  categories: Category[];
  topics: Topic[];
  brandStyle: BrandStyle;
  prompts: PromptTemplate[];
  imageTemplates: ImageTemplate[];
  images: GeneratedImage[];
  posts: GeneratedPost[];
  calendar: CalendarEntry[];
  performance: PerformanceRecord[];
  config: PlatformConfig;
  campaigns: Campaign[];
  publishJobs: PublishJob[];
}

export interface GenerateRequest {
  contentTypeId: ContentTypeId;
  topicId?: string;
  topic?: string;
  categoryId?: string;
  audience?: Audience;
  extraContext?: string;
}
