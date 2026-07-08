import { NextResponse } from "next/server";
import { generateForEntry } from "@/lib/planning/service";

export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const result = await generateForEntry(params.id);
  if (!result) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(result);
}
