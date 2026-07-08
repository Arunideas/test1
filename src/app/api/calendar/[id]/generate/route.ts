import { NextResponse } from "next/server";
import { generateForEntry } from "@/lib/planning/service";
import { AiRequiredError } from "@/lib/service";

export const dynamic = "force-dynamic";

export async function POST(
  _req: Request,
  { params }: { params: { id: string } }
) {
  try {
    const result = await generateForEntry(params.id);
    if (!result) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof AiRequiredError) {
      return NextResponse.json({ error: err.message }, { status: 422 });
    }
    throw err;
  }
}
