import { newId, readDb, updateDb } from "./db";
import type {
  Audience,
  GenerateRequest,
  GeneratedImage,
  GeneratedPost,
  ImageTemplate,
  PostVersion,
  Topic,
} from "./types";
import { getContentType } from "./content/contentTypes";
import { pickHashtags } from "./content/hashtags";
import { analyzeText } from "./voice/styleEngine";
import { buildAltText, buildImagePrompt } from "./image/imagePrompt";
import { renderSvg, svgToDataUri } from "./image/svgRenderer";
import {
  generateImageWithOpenAI,
  generatePostWithLLM,
  hasOpenAI,
} from "./llm/openai";

export class AiRequiredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AiRequiredError";
  }
}

function nowIso(): string {
  return new Date().toISOString();
}

function supportingLines(body: string, hook: string): string[] {
  return body
    .split(/\n+/)
    .map((l) => l.trim())
    .filter((l) => l && l !== hook && !l.startsWith("#") && !l.endsWith("?"));
}

async function createImage(
  template: ImageTemplate,
  topic: string,
  hook: string,
  body: string
): Promise<GeneratedImage> {
  const prompt = buildImagePrompt(template, topic);
  const svg = renderSvg({
    layout: template.layout,
    topic,
    hook,
    lines: supportingLines(body, hook),
  });

  let source: GeneratedImage["source"] = "local-svg";
  let dataForSvgField = svg;

  if (hasOpenAI()) {
    const ai = await generateImageWithOpenAI(prompt);
    if (ai) {
      source = "openai";
      // store the AI image data uri in the svg field (the UI treats it as an <img src>)
      dataForSvgField = ai;
    }
  }

  const image: GeneratedImage = {
    id: newId("img"),
    templateId: template.id,
    layout: template.layout,
    prompt,
    svg: dataForSvgField,
    altText: buildAltText(template, topic),
    source,
    createdAt: nowIso(),
  };
  return image;
}

export interface GenerateResult {
  post: GeneratedPost;
  image: GeneratedImage;
}

export async function generatePost(req: GenerateRequest): Promise<GenerateResult> {
  const db = await readDb();
  const brand = db.brandStyle;
  const ct = getContentType(req.contentTypeId);

  // Resolve topic + category
  let topicText = req.topic?.trim() || "";
  let categoryId = req.categoryId || "";
  let topicId: string | null = req.topicId ?? null;
  let keywords: string[] = [];

  if (req.topicId) {
    const t = db.topics.find((x) => x.id === req.topicId);
    if (t) {
      topicText = t.topic;
      categoryId = t.categoryId;
      keywords = t.keywords;
      topicId = t.id;
    }
  }

  if (!categoryId) {
    categoryId = ct.suggestedCategoryIds[0] || db.categories[0].id;
  }
  const category =
    db.categories.find((c) => c.id === categoryId) || db.categories[0];

  if (!topicText) {
    // auto-pick a topic for this content type that hasn't been generated recently
    const candidate = pickTopicForType(db.topics, ct.suggestedCategoryIds);
    if (candidate) {
      topicText = candidate.topic;
      categoryId = candidate.categoryId;
      keywords = candidate.keywords;
      topicId = candidate.id;
    } else {
      topicText = `${category.name} for the AI era`;
    }
  }

  if (!keywords.length) {
    keywords = topicText
      .toLowerCase()
      .split(/\s+/)
      .filter((w) => w.length > 4)
      .slice(0, 3);
  }

  const audience: Audience = req.audience || ct.defaultAudience;

  // Posts are written by AI only. There is no rule-based fallback.
  if (!hasOpenAI()) {
    throw new AiRequiredError(
      "AI writing is required. Set OPENAI_API_KEY to generate posts."
    );
  }

  const prompt = db.prompts.find((p) => p.contentTypeId === ct.id);
  const llmText = await generatePostWithLLM({
    brand,
    systemHint: prompt?.systemPrompt || ct.blurb,
    topic: topicText,
    audience,
    extra: req.extraContext,
  });

  if (!llmText) {
    throw new AiRequiredError(
      "AI generation failed. Check OPENAI_API_KEY, model access, and try again."
    );
  }

  const engine: GeneratedPost["engine"] = "openai";
  const body = llmText;
  const hook = llmText.split(/\n+/)[0] || topicText;
  const q = llmText.split(/\n+/).find((l) => l.trim().endsWith("?"));
  const cta = q?.trim() || brand.allowedCtas[0];
  const hashtags = pickHashtags(brand, keywords, topicText);

  const analysis = analyzeText(body, brand);

  // Image
  const template =
    db.imageTemplates.find((t) => t.id === (prompt?.imageTemplateId || ct.defaultImageTemplateId)) ||
    db.imageTemplates[0];
  const image = await createImage(template, topicText, hook, body);

  const ts = nowIso();
  const firstVersion: PostVersion = {
    version: 1,
    body,
    imageId: image.id,
    createdAt: ts,
    note: "Generated with OpenAI",
  };

  const post: GeneratedPost = {
    id: newId("post"),
    title: topicText,
    contentTypeId: ct.id,
    categoryId,
    topicId,
    topic: topicText,
    audience,
    body,
    hook,
    cta,
    hashtags,
    imagePrompt: image.prompt,
    imageId: image.id,
    scores: analysis.scores,
    warnings: analysis.warnings,
    wordCount: analysis.wordCount,
    readTimeSeconds: analysis.readTimeSeconds,
    engine,
    status: "draft",
    versions: [firstVersion],
    createdAt: ts,
    updatedAt: ts,
  };

  await updateDb((d) => {
    d.images.push(image);
    d.posts.unshift(post);
    if (topicId) {
      const t = d.topics.find((x) => x.id === topicId);
      if (t) {
        t.lastGeneratedAt = ts;
        t.status = "generated";
      }
    }
  });

  return { post, image };
}

function pickTopicForType(topics: Topic[], categoryIds: string[]) {
  const inScope = topics.filter((t) => categoryIds.includes(t.categoryId));
  const pool = inScope.length ? inScope : topics;
  if (!pool.length) return null;
  // Prefer never-generated, then oldest generated, then highest priority.
  const sorted = [...pool].sort((a, b) => {
    const ax = a.lastGeneratedAt ? Date.parse(a.lastGeneratedAt) : 0;
    const bx = b.lastGeneratedAt ? Date.parse(b.lastGeneratedAt) : 0;
    if (ax !== bx) return ax - bx;
    return b.priority - a.priority;
  });
  return sorted[0];
}

export async function updatePostBody(
  id: string,
  body: string,
  note = "Manual edit"
): Promise<GeneratedPost | null> {
  const db = await readDb();
  const brand = db.brandStyle;
  const analysis = analyzeText(body, brand);
  return updateDb((d) => {
    const post = d.posts.find((p) => p.id === id);
    if (!post) return null;
    const nextVersion = post.versions.length + 1;
    post.versions.push({
      version: nextVersion,
      body,
      imageId: post.imageId,
      createdAt: nowIso(),
      note,
    });
    post.body = body;
    post.hook = body.split(/\n+/)[0] || post.hook;
    post.scores = analysis.scores;
    post.warnings = analysis.warnings;
    post.wordCount = analysis.wordCount;
    post.readTimeSeconds = analysis.readTimeSeconds;
    post.updatedAt = nowIso();
    return post;
  });
}

export async function regenerateImage(
  postId: string,
  templateId?: string
): Promise<{ post: GeneratedPost; image: GeneratedImage } | null> {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === postId);
  if (!post) return null;
  const template =
    db.imageTemplates.find((t) => t.id === templateId) ||
    db.imageTemplates.find((t) => t.id === post.versions[0]?.imageId) ||
    db.imageTemplates[0];
  const image = await createImage(template, post.topic, post.hook, post.body);
  return updateDb((d) => {
    const p = d.posts.find((x) => x.id === postId);
    if (!p) return null;
    d.images.push(image);
    p.imageId = image.id;
    p.imagePrompt = image.prompt;
    p.updatedAt = nowIso();
    return { post: p, image };
  });
}

export async function getPostWithImage(id: string) {
  const db = await readDb();
  const post = db.posts.find((p) => p.id === id);
  if (!post) return null;
  const image = db.images.find((i) => i.id === post.imageId) || null;
  return { post, image };
}

export async function listPosts() {
  const db = await readDb();
  return db.posts.map((p) => ({
    ...p,
    image: db.images.find((i) => i.id === p.imageId) || null,
  }));
}

export async function deletePost(id: string): Promise<boolean> {
  return updateDb((d) => {
    const idx = d.posts.findIndex((p) => p.id === id);
    if (idx === -1) return false;
    d.posts.splice(idx, 1);
    return true;
  });
}
