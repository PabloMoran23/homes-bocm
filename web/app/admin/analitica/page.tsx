import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ADMIN_COOKIE, isValidAdminSession } from "@/lib/admin-auth";
import { getAnalyticsReport } from "@/lib/analytics-report";
import { getDirectoryProject } from "@/lib/project-directory";

export const dynamic = "force-dynamic";
export const metadata = { title: "Analítica · Homes", robots: { index: false, follow: false } };
const LABELS: Record<string, string> = { google: "Google", bing: "Bing", direct: "Directo", internal: "Interno", other: "Otras webs", page_view: "Página", document_click: "Documento", outbound_click: "Enlace externo", boletin_buscar: "Búsqueda en tu zona", estadisticas_filtro: "Filtro de estadísticas", mapa_buscar: "Búsqueda en el mapa", mapa_seleccionar: "Selección en el mapa", ficha_proyecto_ver: "Consulta de ficha", ficha_pestana: "Sección de ficha" };
const label = (s: string) => LABELS[s] || s;
const seconds = (n: number | null) => `${n || 0} s`;
function pageLabel(path: string) {
  const known: Record<string, string> = { "/": "Inicio", "/explore": "Mapa", "/boletin": "Tu zona", "/madrid/estadisticas": "Estadísticas de Madrid", "/ubicacion": "Ficha de ubicación" };
  if (known[path]) return known[path];
  if (path.startsWith("/proyecto/")) {
    try { return getDirectoryProject(decodeURIComponent(path.slice(10)))?.title || path; } catch { return path; }
  }
  return path;
}

export default async function AnalyticsPage({ searchParams }: { searchParams: Promise<{ days?: string; source?: string; traffic?: string }> }) {
  if (!await isValidAdminSession((await cookies()).get(ADMIN_COOKIE)?.value)) redirect("/admin/login?from=/admin/analitica");
  const params = await searchParams;
  const days = [7,30,90].includes(Number(params.days)) ? Number(params.days) : 30;
  const source = ["google","bing","direct","internal","other"].includes(params.source || "") ? params.source! : "all";
  const traffic = ["interesting","bot","admin","unclassified"].includes(params.traffic || "") ? params.traffic! : "all";
  let report;
  try { report = await getAnalyticsReport(days, source, traffic); }
  catch (error) { return <div className="mx-auto max-w-6xl p-8"><h1 className="text-2xl font-semibold">Analítica</h1><p className="mt-4">{error instanceof Error ? error.message : "Analítica no disponible"}</p></div>; }
  const stats = report.overview;
  const cards = [["Sesiones",stats.sessions],["Páginas vistas",stats.pageviews],["Con interacción",stats.active_sessions],["Una sola página",stats.single_page_sessions],["Sin interacción medida",stats.without_interaction],["Actividad media",seconds(stats.avg_active_seconds)]];
  return <div className="mx-auto max-w-6xl space-y-7 px-4 py-8">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-semibold text-slate-900">Cómo se usa Homes</h1><p className="mt-1 text-sm text-slate-600">Sesiones medidas en la web. Últimos {days} días.</p></div><a href="/admin/login" className="text-sm underline">Acceso de administrador</a></header>
    <form className="flex flex-wrap items-end gap-3">
      <label className="text-sm">Periodo<select name="days" defaultValue={days} className="ml-2 rounded border p-2"><option value="7">7 días</option><option value="30">30 días</option><option value="90">90 días</option></select></label>
      <label className="text-sm">Origen<select name="source" defaultValue={source} className="ml-2 rounded border p-2"><option value="all">Todos</option>{["google","bing","direct","internal","other"].map(s=><option key={s} value={s}>{label(s)}</option>)}</select></label>
      <label className="text-sm">Sesiones<select name="traffic" defaultValue={traffic} className="ml-2 rounded border p-2"><option value="all">Todas</option><option value="interesting">Con actividad, sin bots ni admin</option><option value="unclassified">Sin bots ni admin</option><option value="bot">Bots detectados</option><option value="admin">Administradores</option></select></label>
      <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Consultar</button>
    </form>
    <a href={`?days=${days}&source=${source}&traffic=interesting`} className="inline-block text-sm font-medium underline">Ver sesiones con actividad →</a>
    {traffic === "interesting" && <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">Se muestran sesiones con varias páginas, alguna acción o al menos 10 segundos activos. Se excluyen las marcadas como bot o administrador, las rutas de administración y las de más de 100 páginas. Es una selección por comportamiento; no confirma que sean personas. El filtro se aplica también a los totales, páginas, orígenes y recorridos.</p>}
    <p className="rounded-lg bg-slate-100 p-4 text-sm text-slate-600">Una sesión corresponde a una pestaña y caduca tras 30 minutos sin actividad. «Con interacción» significa varias páginas, alguna acción o al menos 10 segundos de actividad. Una sola página no significa que la persona no encontrara la respuesta. Se incluyen administradores y bots que ejecutan la medición. Cada evento indica su tipo de tráfico; «unclassified» no garantiza que sea una persona. {stats.suspicious_sessions > 0 ? `${stats.suspicious_sessions} sesiones tienen más de 100 páginas vistas y se marcan como sospechosas.` : ""}</p>
    <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">{cards.map(([name,value])=><div key={name} className="rounded-xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-500">{name}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}</div>
    {stats.sessions === 0 && <p className="rounded-xl border border-dashed p-6 text-slate-600">Todavía no hay sesiones para este filtro. Los datos se recogen desde la activación de la analítica; no se reconstruyen visitas anteriores.</p>}
    <section><h2 className="mb-3 text-lg font-semibold">Páginas consultadas</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-slate-500"><th className="p-3">Página</th><th>Sesiones</th><th>Vistas</th><th>Actividad media</th><th>Scroll medio</th></tr></thead><tbody>{report.pages.map(p=><tr key={p.path} className="border-b"><td className="max-w-sm break-words p-3"><a className="underline" href={p.path}>{pageLabel(p.path)}</a></td><td>{p.sessions}</td><td>{p.pageviews}</td><td>{seconds(p.active_seconds)}</td><td>{p.scroll_percent || 0}%</td></tr>)}</tbody></table></div></section>
    <div className="grid gap-6 sm:grid-cols-2"><section><h2 className="mb-3 text-lg font-semibold">Origen</h2>{report.sources.map(s=><p key={s.source} className="flex justify-between border-b py-2 text-sm"><span>{label(s.source)}</span><span>{s.sessions} sesiones · {s.pageviews} vistas</span></p>)}</section><section><h2 className="mb-3 text-lg font-semibold">Acciones</h2>{report.actions.map(a=><p key={a.event_name} className="flex justify-between border-b py-2 text-sm"><span>{label(a.event_name)}</span><span>{a.count}</span></p>)}</section></div>
    <section><h2 className="mb-3 text-lg font-semibold">Últimos recorridos</h2><p className="mb-3 text-sm text-slate-500">Hasta 50 sesiones y 60 acciones por recorrido. Los tiempos son aproximados; una pestaña oculta no suma actividad.</p>{report.journeys.map(j=><details key={j.session_id} className="mb-3 rounded-xl border p-4"><summary className="cursor-pointer text-sm"><strong>{label(j.source)}</strong> · {new Date(j.started_at).toLocaleString("es-ES",{timeZone:"Europe/Madrid"})} · {j.pageviews} páginas · {seconds(j.active_seconds)}{j.suspicious ? " · tráfico sospechoso" : ""}<span className="mt-1 block break-all text-slate-500">{j.entry_path}</span></summary><ol className="mt-4 space-y-3 border-l pl-4">{j.events.map(e=><li key={e.id} className="text-sm"><span className="text-xs text-slate-400">{new Date(e.occurred_at).toLocaleTimeString("es-ES",{timeZone:"Europe/Madrid"})}</span> <strong>{label(e.event_name)}</strong><p className="break-all text-slate-600">{e.path}</p>{Object.keys(e.props).length > 0 && <p className="break-all text-xs text-slate-500">{Object.entries(e.props).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>}</li>)}</ol></details>)}</section>
  </div>;
}
