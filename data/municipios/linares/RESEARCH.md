# Linares — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `linares` |
| Provincia | Linares (Jaén) |
| CCAA | Andalucía |
| Boletín | BOJA (`boletin_source_id: boja`) |
| INE | 23069 |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.ciudaddelinares.es | Portal corporativo Drupal 7 |
| Sede electrónica | https://linares.sedelectronica.es | espublico gestiona (TAO 2.0 / ePAC) |
| Tablón de anuncios | https://linares.sedelectronica.es/board | HTML Wicket, ~10 filas visibles + paginación AJAX |
| Catálogo trámites | https://linares.sedelectronica.es/dossier | Trámites urbanismo (sin histórico público) |
| Consulta expedientes | https://linares.sedelectronica.es/expedientes | Requiere Cl@ve/certificado digital |
| Área urbanismo | https://www.ciudaddelinares.es/areas-municipales?area=urbanismo-y-medio-ambiente | Información del área |
| Documentación urbanismo | https://www.ciudaddelinares.es/areas-municipales/documentacion/urbanismo-y-medio-ambiente | PDFs juntas de compensación, sectores, UE |
| Descarga instancias | https://www.ciudaddelinares.es/tramites/descarga-instancias | Formularios licencias/DR/comunicación previa |
| Ordenanzas | https://www.ciudaddelinares.es/normativa/ordenanzas-reglamentos | Ordenanzas fiscales y urbanísticas |
| Geoportal industrial | https://www.ciudaddelinares.es/interes/geoportal-industrial-info | Visor eMap400 (planeamiento industrial) |
| Visor mapas SIG | http://gis.ciudaddelinares.es/emap400/emapsearch.aspx?prjid=geoportal&scope=PLANEAM&ortho=true&lang=3 | Visor Flash legacy |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOU vigente (consulta regional) |

## Cómo se listan expedientes / proyectos

1. **Tablón sede espublico**: HTML con filas `<tr>` y celdas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Paginación vía Wicket AJAX (10 filas/página).
2. **Documentación urbanismo (Drupal)**: listado estático de PDFs de juntas de compensación por sector/UE (plan parcial sector 6, sector 22, plan especial Cánovas del Castillo, etc.).
3. **SITUA**: enlace de consulta al planeamiento general aprobado en Junta de Andalucía (sin scrape de geometría por expediente).
4. **Consulta expedientes sede**: requiere autenticación; no hay listado público de expedientes urbanísticos individuales.

## Cómo se publican licencias

- **Tablón sede**: edictos y notificaciones (p. ej. «Licencias de Actividad»); sin dataset histórico completo.
- **Descarga instancias (Drupal)**: formularios PDF para comunicación previa, declaración responsable, cambio de uso, obras menores — no concesiones individuales.
- **Catálogo sede /dossier**: trámites electrónicos de solicitud (sin listado de concesiones).
- No hay dataset abierto de licencias con coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - `gis.ciudaddelinares.es/emap400/` — visor eMap400 (Flash), sin REST/ArcGIS/WFS accesible desde automatización; timeout en probes.
  - Geoportal industrial — capas de planeamiento y polígonos industriales; sin enlace a código de expediente del tablón.
  - SITUA/VITUA (Junta de Andalucía) — instrumentos de planeamiento general (PGOU), no geometría por licencia/expediente municipal.
  - Diputación de Jaén IDE (`ide.dipujaen.es`) — excluye Jaén y Linares (>50.000 hab.).
- **Estrategia:** sin fuente GIS consultable por expediente; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** visor Flash obsoleto; expedientes en ePAC/Pac requieren login; tablón solo PDFs sin georreferencia.

## Limitaciones

- Tablón sede: paginación AJAX Wicket (solo primera página scrapeada de forma fiable).
- Consulta de expedientes urbanísticos requiere identificación electrónica.
- Sin visor urbanístico interactivo con API pública enlazada a expedientes.
- Gestión dual Pac + ePAC documentada en PDF corporativo (convivencia de sistemas).
