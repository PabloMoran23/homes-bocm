import Link from "next/link";
import styles from "./ExploreAreaBanner.module.css";

export function ExploreAreaBanner() {
  return <aside className={styles.banner} aria-label="Descubre Tu zona">
    <div className={styles.icon} aria-hidden="true">
      <svg width="48" height="48" viewBox="0 0 40 40" fill="none"><circle cx="20" cy="20" r="18" stroke="currentColor" strokeDasharray="2 4" /><path d="M27 17c0 5-7 11-7 11s-7-6-7-11a7 7 0 1 1 14 0Z" stroke="currentColor" strokeWidth="1.5" /><circle cx="20" cy="17" r="2.5" stroke="currentColor" strokeWidth="1.5" /></svg>
    </div>
    <div className={styles.copy}><p className={styles.kicker}>La ciudad también cambia a tu alrededor</p><h2>Descubre qué está cambiando cerca de ti.</h2><p className={styles.description}>Busca una dirección y conoce los proyectos, las obras y las últimas aprobaciones de su entorno.</p></div>
    <div className={styles.action}><Link href="/boletin">Explorar mi zona <span aria-hidden="true">↗</span></Link><span>Consulta la cobertura de tu municipio</span></div>
  </aside>;
}
