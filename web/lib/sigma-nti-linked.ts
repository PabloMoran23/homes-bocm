import { expedienteGrupoKeyFromVariant } from "@/lib/madrid-expediente";

export type SigmaNtiLinkedDoc = {
  orden: number | null;
  url: string;
  titulo: string | null;
  tooltip: string | null;
  rutaCarpetas: string | null;
  tipodocNti: string | null;
  fechaDocumento: string | null;
  localPath: string | null;
  sha256: string | null;
  fileBytes: number | null;
  contentType: string | null;
  httpStatus: number | null;
  downloadError: string | null;
};

export type SigmaNtiLinkedGrupo = {
  stats: {
    total: number;
    downloaded: number;
    errors: number;
    bytesTotal: number;
  };
  documentos: SigmaNtiLinkedDoc[];
};

export type SigmaNtiLinkedBundle = {
  generatedAt: string;
  expedienteCount: number;
  documentCount: number;
  byGrupo: Record<string, SigmaNtiLinkedGrupo>;
};

let cache: Promise<SigmaNtiLinkedBundle | null> | null = null;

export function loadSigmaNtiLinkedBundle(): Promise<SigmaNtiLinkedBundle | null> {
  if (!cache) {
    cache = (async () => {
      try {
        const res = await fetch("/data/sigma-nti-linked.json");
        if (!res.ok) return null;
        return (await res.json()) as SigmaNtiLinkedBundle;
      } catch {
        return null;
      }
    })();
  }
  return cache;
}

export function sigmaNtiGrupoFromExpediente(expediente: string): string {
  return expedienteGrupoKeyFromVariant(expediente);
}

export function lookupSigmaNtiGrupo(
  bundle: SigmaNtiLinkedBundle | null,
  expediente: string | null | undefined,
): SigmaNtiLinkedGrupo | null {
  if (!bundle || !expediente) return null;
  const g = sigmaNtiGrupoFromExpediente(expediente);
  return bundle.byGrupo[g] ?? null;
}

export function formatBytes(n: number | null | undefined): string {
  if (n == null || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
