import { NextResponse } from "next/server";
import { readDb } from "@/lib/db";
import { CONTENT_TYPES } from "@/lib/content/contentTypes";
import { hasOpenAI } from "@/lib/llm/openai";

export const dynamic = "force-dynamic";

export async function GET() {
  const db = await readDb();
  return NextResponse.json({
    contentTypes: CONTENT_TYPES,
    categories: db.categories,
    imageTemplates: db.imageTemplates,
    brandStyle: db.brandStyle,
    prompts: db.prompts,
    topics: db.topics,
    engine: hasOpenAI() ? "openai" : "rule-based",
  });
}
