import { LICENCIA_MAPA_CONFIG, LICENCIA_MAPA_LEYENDA } from "@/lib/licencia-mapa";

export function LicenciaMapLegend({
  className = "",
  layout = "stack",
}: {
  className?: string;
  layout?: "stack" | "grid";
}) {
  const layoutClass =
    layout === "grid"
      ? "grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3"
      : "flex flex-col gap-1";
  return (
    <div className={`${layoutClass} ${className}`}>
      {LICENCIA_MAPA_LEYENDA.map((cat) => {
        const cfg = LICENCIA_MAPA_CONFIG[cat];
        return (
          <span key={cat} className="flex items-center gap-2">
            <span
              className="h-3 w-3 shrink-0 rounded-full ring-2 ring-white"
              style={{ backgroundColor: cfg.bg, boxShadow: `0 0 0 1px ${cfg.ring}` }}
            />
            <span>{cfg.label}</span>
          </span>
        );
      })}
    </div>
  );
}
