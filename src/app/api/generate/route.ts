import { NextResponse } from "next/server";
import { AiRequiredError, generatePost } from "@/lib/service";
import type { GenerateRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as GenerateRequest;
    if (!body?.contentTypeId) {
      return NextResponse.json(
        { error: "contentTypeId is required" },
        { status: 400 }
      );
    }
    const result = await generatePost(body);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof AiRequiredError) {
      return NextResponse.json({ error: err.message }, { status: 422 });
    }
    console.error("generate error", err);
    return NextResponse.json(
      { error: "Failed to generate content" },
      { status: 500 }
    );
  }
}
