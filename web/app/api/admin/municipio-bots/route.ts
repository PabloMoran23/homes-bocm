import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { join } from "node:path";
import { NextResponse } from "next/server";
import type { MunicipioBotsPayload } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const execFileAsync = promisify(execFile);

export async function GET() {
  const webRoot = process.cwd();
  const pocRoot = join(webRoot, "..");

  try {
    const { stdout, stderr } = await execFileAsync(
      "python3",
      ["-m", "municipio", "export-admin"],
      {
        cwd: pocRoot,
        env: { ...process.env, PYTHONPATH: pocRoot },
        maxBuffer: 24 * 1024 * 1024,
        timeout: 120_000,
      },
    );
    if (stderr?.trim()) {
      console.warn("municipio-bots stderr:", stderr.slice(0, 500));
    }
    const data = JSON.parse(stdout) as MunicipioBotsPayload;
    return NextResponse.json(data, {
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    const fallback: MunicipioBotsPayload = {
      generatedAt: new Date().toISOString(),
      queueUpdatedAt: null,
      dbAvailable: false,
      summary: {
        total: 0,
        byStatus: {},
        byComunidad: {},
        withManifest: 0,
        withAdapter: 0,
        mergedOrSkipped: 0,
        parityOk: 0,
        withPortalGeometry: 0,
        openPrs: 0,
        live: {
          fresh: 0,
          due: 0,
          never: 0,
          error: 0,
          withLastIngest: 0,
          totalProyectos: 0,
          totalLicencias: 0,
        },
        completeness: {
          avgScore: 0,
          byBand: { rico: 0, medio: 0, basico: 0, fino: 0, sin_datos: 0 },
          withPdf: 0,
          withGeometry: 0,
          withCoords: 0,
          withExpediente: 0,
          scoredAdapters: 0,
        },
      },
      next: null,
      openPrsBySlug: {},
      municipios: [],
    };
    return NextResponse.json({ ...fallback, error: msg }, { status: 200 });
  }
}
