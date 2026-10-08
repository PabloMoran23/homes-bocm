import Link from "next/link";
type Props = { planesCount?: number; licenciasCount?: number; latestLicenciasYear?: number; latestLicenciasTotal?: number; topDistritos?: { name: string; count: number }[] };
export function LandingDashboardSection({ planesCount, licenciasCount, topDistritos = [] }: Props) {
  const max = Math.max(1, ...topDistritos.map(d => d.count));
  return <section className="landing-analysis" aria-labelledby="landing-dashboard-heading"><div className="landing-analysis-inner">
    <div><p className="landing-eyebrow">Observatorio · Madrid capital</p><h2 id="landing-dashboard-heading">Pon los proyectos<br />en perspectiva.</h2><p>Compara licencias por distrito, revisa la evolución de la actividad y profundiza en el planeamiento de la ciudad.</p><Link href="/madrid/estadisticas">Abrir el panel de análisis ↗</Link></div>
    <div className="landing-analysis-data"><p className="landing-analysis-label">Base de análisis · Madrid</p><div className="landing-analysis-counts">{[{n: licenciasCount, label: "licencias registradas"}, {n: planesCount, label: "expedientes de planeamiento"}].filter(item => item.n != null).map(item => <div key={item.label}><strong>{item.n?.toLocaleString("es-ES")}</strong><span>{item.label}</span></div>)}</div>
      {topDistritos.length > 0 ? <div className="landing-analysis-bars">{topDistritos.map(d => <div key={d.name}><span>{d.name}</span><i style={{width: `${Math.max(8, d.count / max * 100)}%`}}/><small>{d.count.toLocaleString("es-ES")}</small></div>)}</div> : <div className="landing-analysis-topics"><span>01 / Evolución anual</span><span>02 / Actividad por distrito</span><span>03 / Planeamiento</span></div>}
    </div>
  </div></section>;
}
