import type { DashboardView, KpiModel, RankRow, RecentModel } from "@/lib/analytics-dashboard";
import type { DeltaModel } from "@/lib/analytics-format";

export function AnalyticsBody({ view }: { view: DashboardView }) {
  return (
    <div className="space-y-4">
      {view.alert ? (
        <section className="rounded-2xl border border-[#e4c2b2] bg-[#fbf4ef] px-4 py-3 text-sm text-[#6a3b30]">
          <h2 className="font-semibold">{view.alert.title}</h2>
          <p className="mt-1 leading-relaxed">{view.alert.body}</p>
        </section>
      ) : null}
      <section className="grid grid-cols-2 gap-3 xl:grid-cols-6">
        {view.kpis.map((kpi) => (
          <KpiCard key={kpi.id} kpi={kpi} />
        ))}
      </section>
      {view.empty ? (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white/70 px-4 py-6 text-sm text-slate-600">
          Todavía no hay sesiones para este filtro. La medición no reconstruye visitas anteriores a su activación.
        </p>
      ) : null}
    </div>
  );
}

function KpiCard({ kpi }: { kpi: KpiModel }) {
  return (
    <article className="rounded-2xl border border-[rgba(42,38,34,0.08)] bg-white px-4 py-3 shadow-sm">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{kpi.label}</h2>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-[var(--portal-ink)]">{kpi.value}</p>
      {kpi.detail ? <p className="mt-1 min-h-8 text-xs leading-snug text-slate-500">{kpi.detail}</p> : <div className="mt-1 min-h-8" />}
      <Delta delta={kpi.delta} invert={kpi.invert} />
    </article>
  );
}

function Delta({ delta, invert = false }: { delta: DeltaModel; invert?: boolean }) {
  const positive = delta.direction === "up";
  const negative = delta.direction === "down";
  const good = invert ? negative : positive;
  const bad = invert ? positive : negative;
  const color = good ? "text-emerald-800" : bad ? "text-rose-800" : "text-slate-500";
  const arrow = delta.direction === "up" ? "↑" : delta.direction === "down" ? "↓" : "";
  return (
    <p className={`mt-2 text-xs font-medium ${color}`}>
      {arrow ? <span aria-hidden="true">{arrow} </span> : null}
      {delta.text}
      {delta.direction === "up" || delta.direction === "down" ? <span className="sr-only"> respecto al periodo anterior</span> : null}
    </p>
  );
}

export function RankList({
  title,
  subtitle,
  rows,
  empty,
}: {
  title: string;
  subtitle?: string;
  rows: RankRow[];
  empty: string;
}) {
  const max = Math.max(1, ...rows.map((row) => row.value));
  return (
    <section className="rounded-2xl border border-[rgba(42,38,34,0.08)] bg-white shadow-sm">
      <header className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{subtitle}</p> : null}
      </header>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-slate-500">{empty}</p>
      ) : (
        <ol>
          {rows.map((row) => (
            <li key={row.key} className="border-b border-slate-100 px-4 py-3 last:border-b-0">
              <div className="flex items-baseline justify-between gap-3">
                {row.href ? (
                  <a href={row.href} className="min-w-0 break-words text-sm font-medium text-[var(--portal-accent)] underline-offset-2 hover:underline">
                    {row.label}
                  </a>
                ) : (
                  <span className="min-w-0 break-words text-sm font-medium text-slate-800">{row.label}</span>
                )}
                <span className="shrink-0 text-sm tabular-nums text-slate-700">{row.valueLabel}</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--portal-paper-deep)]">
                <div className="h-full rounded-full bg-[var(--portal-accent)]" style={{ width: `${Math.max(4, (row.value / max) * 100)}%` }} />
              </div>
              {row.hint ? <p className="mt-1 text-xs text-slate-500">{row.hint}</p> : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function RecentSessions({ rows }: { rows: RecentModel[] }) {
  return (
    <section className="rounded-2xl border border-[rgba(42,38,34,0.08)] bg-white shadow-sm">
      <header className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">Sesiones recientes</h2>
        <p className="mt-0.5 text-xs text-slate-500">Hasta 12 sesiones del filtro. Sin el detalle de cada evento.</p>
      </header>
      {rows.length === 0 ? (
        <p className="px-4 py-6 text-sm text-slate-500">No hay sesiones en este filtro.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-2 font-medium">Cuándo</th>
                <th className="px-2 py-2 font-medium">Tipo</th>
                <th className="px-2 py-2 font-medium">Origen</th>
                <th className="px-2 py-2 font-medium">Entrada</th>
                <th className="px-2 py-2 font-medium">Páginas</th>
                <th className="px-4 py-2 font-medium">Tiempo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-t border-slate-100">
                  <td className="whitespace-nowrap px-4 py-2 text-slate-700">{row.when}</td>
                  <td className="px-2 py-2">
                    <span className={trafficClass(row.trafficKey)}>{row.traffic}</span>
                    {row.suspicious ? <span className="ml-2 text-xs text-rose-700">+100 páginas</span> : null}
                  </td>
                  <td className="px-2 py-2 text-slate-700">{row.source}</td>
                  <td className="max-w-xs px-2 py-2">
                    {row.href ? (
                      <a href={row.href} className="break-words text-[var(--portal-accent)] underline-offset-2 hover:underline">
                        {row.entry}
                      </a>
                    ) : (
                      row.entry
                    )}
                  </td>
                  <td className="px-2 py-2 tabular-nums">{row.pageviews}</td>
                  <td className="px-4 py-2 tabular-nums text-slate-700">{row.active}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function trafficClass(traffic: string): string {
  if (traffic === "bot") return "rounded-full bg-[#f6e6e0] px-2 py-0.5 text-xs font-semibold text-[#7a4638]";
  if (traffic === "admin") return "rounded-full bg-[#f8ecd8] px-2 py-0.5 text-xs font-semibold text-[#7a5a22]";
  return "rounded-full bg-[#e5eeea] px-2 py-0.5 text-xs font-semibold text-[#1f4f53]";
}

export function ReadingNotes() {
  return (
    <details className="rounded-2xl border border-[rgba(42,38,34,0.08)] bg-white/80 px-4 py-3 text-sm text-slate-600">
      <summary className="cursor-pointer font-medium text-slate-800">Cómo leer estos datos</summary>
      <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed">
        <li>Una sesión es una pestaña y caduca tras 30 minutos sin actividad. No identifica a la persona ni une días distintos.</li>
        <li>Persona significa que el evento no llegó marcado como bot ni como administrador. No confirma que haya una persona detrás.</li>
        <li>El rebote aproximado es una sola página, sin acción medida y con menos de 10 segundos activos. No es comparable con otra herramienta.</li>
        <li>Abrir una ficha no cuenta como acción. Sí cuentan documentos, enlaces, búsquedas, filtros y pestañas.</li>
        <li>Las fichas de ubicación se agrupan en /ubicacion. No hay dispositivo ni user-agent guardado en los eventos.</li>
        <li>El primer y el último tramo pueden estar incompletos. La comparación usa un periodo anterior de la misma duración.</li>
      </ul>
    </details>
  );
}
