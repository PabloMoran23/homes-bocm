import { LICENCIA_MAPA_CONFIG, LICENCIA_MAPA_LEYENDA } from "@/lib/licencia-mapa";

export function LicenciaMapLegend({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
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
