import { NextResponse } from "next/server";
import { listPosts } from "@/lib/service";

export const dynamic = "force-dynamic";

export async function GET() {
  const posts = await listPosts();
  return NextResponse.json({ posts });
}
