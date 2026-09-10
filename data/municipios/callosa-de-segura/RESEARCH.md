# Callosa de Segura — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (WordPress) | https://www.callosadesegura.es |
| Sede electrónica (espublico gestiona) | https://callosadesegura.sedelectronica.es |
| Tablón de anuncios | https://callosadesegura.sedelectronica.es/board// |
| Transparencia (urbanismo, 29 docs) | https://callosadesegura.sedelectronica.es/transparency/ |
| PGOU (PDFs estáticos) | https://www.callosadesegura.es/el-ayuntamiento/concejalias/obras-y-servicios/plan-general-ordenacion-urbana/ |
| Urbanismo concejalía | https://www.callosadesegura.es/el-ayuntamiento/concejalias/urbanismo-y-accesibilidad-urbana/ |
| Agenda urbana | https://www.callosadesegura.es/el-ayuntamiento/agenda-urbana/ |
| Consulta expedientes (login) | https://callosadesegura.sedelectronica.es/expedientes |

## Proyectos / planeamiento

- **PGOU:** 25 PDFs en `/impresos/pgou/` (planos por hojas p0–p5, normas, ordenanzas, catálogo) + edicto/memoria/ordenanzas modificación 2023 en `wp-content/uploads/2023/11/`.
- **Tablón sede:** HTML tabular Wicket (espublico); primera página ~10 filas; filtrado por keywords urbanismo (expropiaciones, licencias actividad, etc.).
- **Noticias urbanismo:** categoría WP `/category/noticias/concejalias/urbanismo/` (noticias puntuales, no listado estructurado de expedientes).
- **Consulta expedientes:** requiere autenticación Cl@ve; no hay API pública.

## Licencias

- **Tablón:** edictos de licencias de actividad (p. ej. ampliación horarios hostelería).
- **e-trámites WordPress:** declaraciones responsables (obras menores, primera/segunda ocupación), licencia parcelación, certificado compatibilidad, información urbanística, licencia ambiental.
- **Sin registro histórico** de concesiones publicadas; el adapter incluye fichas informativas de trámites (patrón Pozuelo/Benigànim).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `Planeamiento.Zonificacion`
  - Filtro: `cod_ine_mun = 03009` (Callosa de Segura, Alicante)
  - ~20 polígonos: PGOU municipal, plan parcial "El Clerigo", Castellar, Solana, Sargento, etc.
- **Estrategia:** paginación WFS (`startIndex` 0–13500, count 500) + match por keywords en título (plan general, sector, plan parcial). Merge MultiPolygon para PGOU.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→geometría en tablón.
  - WFS cubre zonificación/planeamiento aprobado, no licencias de obra individuales.
  - Transparencia sede usa Wicket AJAX (no scrapeado; duplica tablón en muchos casos).
  - PDFs PGOU sin georreferencia embebida.

## Limitaciones generales

- Tablón paginado vía Wicket (solo primera página en scrape determinista).
- SSL sede: certificado válido; `insecure_ssl` habilitado por compatibilidad con otros espublico.
- Provincia en `queue.yaml` aparece como nombre municipio; INE provincia = Alicante (03).
