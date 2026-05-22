import { NextResponse } from "next/server";
import { publicRegistry } from "../../lib/registry";

export async function GET() {
  return NextResponse.json({ tools: publicRegistry() });
}
