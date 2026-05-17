import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { join } from "node:path";
import { NextResponse } from "next/server";
import type { PipelineStatusPayload } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const execFileAsync = promisify(execFile);

export async function GET() {
  const webRoot = process.cwd();
  const pocRoot = join(webRoot, "..");
  const script = join(pocRoot, "db", "pipeline_status_json.py");

  try {
    const { stdout, stderr } = await execFileAsync("python3", [script, pocRoot], {
      cwd: pocRoot,
      maxBuffer: 12 * 1024 * 1024,
      timeout: 15_000,
    });
    if (stderr?.trim()) {
      console.warn("pipeline-status stderr:", stderr.slice(0, 500));
    }
    const data = JSON.parse(stdout) as PipelineStatusPayload;
    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "no-store, max-age=0",
      },
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    const fallback: PipelineStatusPayload = {
      generatedAt: new Date().toISOString(),
      pocRoot,
      sqlite: {},
      visorJson: {},
      log: {
        phase: "error",
        fetchCurrent: null,
        fetchTotal: null,
        lastLines: [],
        errorLineCount: 1,
        errorSample: [msg],
      },
      error: msg,
    };
    return NextResponse.json(fallback, { status: 200 });
  }
}
