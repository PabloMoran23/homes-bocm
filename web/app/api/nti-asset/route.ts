import { createReadStream, existsSync, statSync } from "node:fs";
import { join, normalize, resolve } from "node:path";
import { Readable } from "node:stream";
import { NextRequest, NextResponse } from "next/server";

const NTI_ROOT = resolve(join(process.cwd(), "..", "output", "madrid_nti_downloads"));

const MIME: Record<string, string> = {
  ".pdf": "application/pdf",
  ".zip": "application/zip",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".txt": "text/plain",
  ".doc": "application/msword",
};

function resolveSafePath(raw: string): string | null {
  if (!raw || raw.includes("..")) return null;
  const rel = normalize(raw.replace(/^madrid_nti_downloads[/\\]/, "")).replace(
    /^(\.\.(\/|\\|$))+/,
    "",
  );
  const abs = resolve(join(NTI_ROOT, rel));
  if (abs !== NTI_ROOT && !abs.startsWith(`${NTI_ROOT}/`)) return null;
  return abs;
}

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("path");
  const abs = raw ? resolveSafePath(raw) : null;
  if (!abs || !existsSync(abs) || !statSync(abs).isFile()) {
    return NextResponse.json({ error: "no encontrado" }, { status: 404 });
  }

  const ext = abs.slice(abs.lastIndexOf(".")).toLowerCase();
  const type = MIME[ext] || "application/octet-stream";
  const name = encodeURIComponent(abs.split("/").pop() || "documento");
  const stream = Readable.toWeb(createReadStream(abs)) as ReadableStream<Uint8Array>;

  return new NextResponse(stream, {
    headers: {
      "Content-Type": type,
      "Content-Disposition": `inline; filename*=UTF-8''${name}`,
    },
  });
}
