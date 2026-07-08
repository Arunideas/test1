import { NextResponse } from "next/server";
import { deletePost, getPostWithImage, updatePostBody } from "@/lib/service";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const result = await getPostWithImage(params.id);
  if (!result) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(result);
}

export async function PUT(
  req: Request,
  { params }: { params: { id: string } }
) {
  const body = (await req.json()) as { body?: string; note?: string };
  if (typeof body.body !== "string") {
    return NextResponse.json({ error: "body is required" }, { status: 400 });
  }
  const post = await updatePostBody(params.id, body.body, body.note);
  if (!post) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ post });
}

export async function DELETE(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const ok = await deletePost(params.id);
  return NextResponse.json({ ok });
}
