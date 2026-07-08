import type {
  Audience,
  BrandStyle,
  Category,
  ContentTypeId,
  Topic,
} from "../types";
import { analyzeText, pickCta } from "../voice/styleEngine";

export interface DraftPost {
  title: string;
  hook: string;
  body: string;
  cta: string;
  hashtags: string[];
}

function hashOf(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

function pick<T>(arr: T[], seed: number): T {
  return arr[seed % arr.length];
}

function pickHashtags(brand: BrandStyle, keywords: string[], seed: number): string[] {
  const tags = new Set<string>();
  for (const k of keywords) {
    const clean = k.replace(/[^a-z0-9]/gi, "");
    if (clean.length > 2) tags.add("#" + clean.charAt(0).toUpperCase() + clean.slice(1));
  }
  const pool = brand.hashtagPool;
  let i = seed;
  while (tags.size < 4 && pool.length) {
    tags.add(pool[i % pool.length]);
    i++;
  }
  return [...tags].slice(0, 5);
}

interface Ctx {
  topic: string;
  keywords: string[];
  category: Category;
  audience: Audience;
  brand: BrandStyle;
  seed: number;
  extra?: string;
}

// Each builder returns the middle blocks (problem, evidence, solution, action).
type Builder = (c: Ctx) => { hook: string; blocks: string[] };

const BUILDERS: Record<ContentTypeId, Builder> = {
  resume_review: (c) => ({
    hook: pick(
      [
        "Most resumes get rejected before anyone reads them properly.",
        "Recruiters spend about 7 seconds on your resume.",
        "A weak first line quietly costs students interviews.",
      ],
      c.seed
    ),
    blocks: [
      "The problem is not effort. It is order.\nThe most important line sits below the fold.",
      "Across the resumes we review, the same pattern shows up.\nThe top third: a photo, an objective, and soft skills.\nNone of it answers the recruiter's real question.",
      "Fix the top third first.\nName your role and one result with a number.\nThen list the tools you actually used.",
      "Cut every adjective with no proof behind it.\n\"Hardworking\" means nothing.\n\"Shipped 3 projects\" does.",
    ],
  }),

  ai_tool_of_the_week: (c) => ({
    hook: pick(
      [
        "Most students open an AI tool and freeze at the blank box.",
        "An AI tool is only useful if it finishes one real task.",
        "You don't need ten AI tools. You need one, used well.",
      ],
      c.seed
    ),
    blocks: [
      `This week: a practical way to use AI for ${c.topic.toLowerCase()}.`,
      "Pick one task you already have.\nA resume bullet, a cover note, a project summary.\nGive the tool your rough draft, not a blank prompt.",
      "Ask it to tighten, not to invent.\nInvented details break in interviews.\nYour own facts, phrased clearly, hold up.",
      "One limit worth knowing.\nIt will sound confident even when it is wrong.\nAlways check names, numbers and dates yourself.",
    ],
  }),

  recruiter_tips: (c) => ({
    hook: pick(
      [
        "From the recruiter's side, most applications look the same.",
        "Recruiters are not looking for perfect. They are looking for clear.",
        "The gap is rarely skill. It is how the skill is shown.",
      ],
      c.seed
    ),
    blocks: [
      "When a recruiter opens 200 applications, they scan for signal.\nRelevant project, real result, matching skill.",
      "What gets skipped: long summaries, generic objectives, and skills with no evidence.\nNot because they are bad. Because they are slow to read.",
      "If you are a student, make the signal obvious.\nMatch three keywords from the role.\nShow one result per project.",
      "If you are hiring, tell applicants what signal you want.\nClear job posts get clearer applicants.",
    ],
  }),

  ai_career: (c) => ({
    hook: pick(
      [
        "The AI era did not remove jobs for students. It moved the starting line.",
        "You do not need to predict the future to prepare for it.",
        "One skill compounds faster than the rest right now.",
      ],
      c.seed
    ),
    blocks: [
      `Take ${c.topic.toLowerCase()}.\nIt sounds big. In practice it starts small.`,
      "A realistic way to begin in 4 weeks:\nWeek 1: learn the basics from one free course.\nWeek 2: rebuild one thing you use daily.",
      "Week 3: break it, then fix it.\nWeek 4: write down what you learned in public.",
      "You are not aiming for expert.\nYou are aiming for evidence you can point to.",
    ],
  }),

  student_tips: (c) => ({
    hook: pick(
      [
        "A final year student asked us a simple question last week.",
        "Most students prepare for the wrong part of the interview.",
        "One small habit separates the students who get callbacks.",
      ],
      c.seed
    ),
    blocks: [
      `The topic was ${c.topic.toLowerCase()}.\nThe honest answer is less exciting than the advice online.`,
      "Preparation beats talent here.\nWrite your three strongest stories before the interview.\nUse real projects, not made-up wins.",
      "Structure it: situation, what you did, what changed.\nKeep it under a minute.\nStop when the point lands.",
      "Then practice out loud once.\nReading it is not the same as saying it.",
    ],
  }),

  hiring_tips: (c) => ({
    hook: pick(
      [
        "Hiring interns is slow for a boring reason: unclear scope.",
        "Most internship programs fail in week one, not month three.",
        "You can hire pre-assessed interns fast without lowering the bar.",
      ],
      c.seed
    ),
    blocks: [
      "The delay is rarely the candidate.\nIt is the loop: post, wait, screen, repeat.",
      "A tighter pipeline looks like this.\nDefine one clear task the intern will own.\nAssess for that task, not for a general resume.",
      "Give a short, role-based assignment.\nReview signal, not polish.\nMove the top few to a 20-minute call.",
      "A clear scope shortens hiring to days.\nIt also makes the internship worth the intern's time.",
    ],
  }),

  linkedin_post: (c) => ({
    hook: pick(
      [
        `Here is a simple way to think about ${c.topic.toLowerCase()}.`,
        "Most advice on this is either too vague or too salesy.",
        "This one is easy to ignore and expensive to skip.",
      ],
      c.seed
    ),
    blocks: [
      `The question underneath ${c.topic.toLowerCase()} is trust.\nIs this real, and is it worth my time?`,
      "A few checks make the answer clear.\nWho is behind it. What they actually offer. Whether the details add up.",
      "Do the boring checks first.\nSearch the name. Read past posts. Look for specifics, not promises.",
      "If something feels off, it usually is.\nSlow down before you commit time or money.",
    ],
  }),
};

export function generateDraft(
  contentTypeId: ContentTypeId,
  topic: string,
  category: Category,
  audience: Audience,
  brand: BrandStyle,
  keywords: string[],
  extra?: string
): DraftPost {
  const seed = hashOf(topic + contentTypeId + (extra ?? ""));
  const builder = BUILDERS[contentTypeId] ?? BUILDERS.linkedin_post;
  const { hook, blocks } = builder({
    topic,
    keywords,
    category,
    audience,
    brand,
    seed,
    extra,
  });

  const cta = pickCta(brand, seed);

  const parts: string[] = [hook, ...blocks];
  if (extra && extra.trim()) {
    parts.push(extra.trim());
  }
  parts.push(cta);

  const body = parts.join("\n\n");
  const hashtags = pickHashtags(brand, keywords, seed);
  const title = topic;

  return { title, hook, body, cta, hashtags };
}

export function scoreDraft(body: string, brand: BrandStyle) {
  return analyzeText(body, brand);
}
