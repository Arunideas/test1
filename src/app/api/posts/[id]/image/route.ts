import { NextResponse } from "next/server";
import { regenerateImage } from "@/lib/service";

export const dynamic = "force-dynamic";

export async function POST(
  req: Request,
  { params }: { params: { id: string } }
) {
  const body = (await req.json().catch(() => ({}))) as { templateId?: string };
  const result = await regenerateImage(params.id, body.templateId);
  if (!result) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(result);
}
