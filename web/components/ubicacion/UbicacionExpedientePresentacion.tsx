import { SigmaClassificationIcon } from "@/components/sigma/SigmaClassificationIcon";
import {
  categoriaExpedienteLabel,
  clasificarExpediente,
} from "@/lib/ubicacion-resumen";
import type { SigmaClassification } from "@/lib/sigma-classification";
import {
  sigmaClassificationHeroToneClass,
  sigmaHeroClassificationHeadline,
} from "@/lib/sigma-classification-icon";
import { sigmaPickDisplayHeadline } from "@/lib/sigma-presentation";
import type { SigmaExpedienteMetric } from "@/lib/sigma-metrics";
import type { UbicacionSigmaExpediente } from "@/lib/ubicacion";

export function UbicacionExpedientePresentacion({
  exp,
  metric,
  clasificacion,
  compact = false,
  iconSize = compact ? "sm" : "md",
  showIcon = true,
}: {
  exp: UbicacionSigmaExpediente;
  metric: SigmaExpedienteMetric | null;
  clasificacion: SigmaClassification | null;
  compact?: boolean;
  iconSize?: "sm" | "md" | "hero";
  showIcon?: boolean;
}) {
  const classHeadline = sigmaHeroClassificationHeadline(clasificacion);
  const { title: projectName } = sigmaPickDisplayHeadline({
    expedienteGrupo: exp.expediente_grupo,
    denominacion: exp.denominacion,
    fase: exp.fase,
    metric,
  });
  const classificationTitle =
    classHeadline?.title ?? categoriaExpedienteLabel(clasificarExpediente(exp));

  return (
    <div className={`flex min-w-0 items-start ${showIcon ? "gap-3" : ""}`}>
      {showIcon ? <SigmaClassificationIcon clasificacion={clasificacion} size={iconSize} /> : null}
      <div className="min-w-0 flex-1">
        <p
          className={`break-words font-semibold leading-tight ${sigmaClassificationHeroToneClass(clasificacion)} ${
            compact ? "text-sm" : "text-base sm:text-lg"
          }`}
        >
          {classificationTitle}
        </p>
        <p
          className={`mt-1 break-words font-bold leading-snug text-slate-900 ${
            compact ? "line-clamp-3 text-xs" : "text-sm sm:text-base"
          }`}
        >
          {projectName}
        </p>
      </div>
    </div>
  );
}
