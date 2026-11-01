# Totana — investigación portal ayuntamiento

Municipio: **Totana** (`totana`) — Murcia, Región de Murcia. INE **30039**. Sin boletín regional asociado en cola.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.totana.es |
| Concejalía Urbanismo | http://www.totana.es/concejalias/concejalia.asp?id=35 |
| RSS noticias Urbanismo | https://www.totana.es/noticiasrss.asp?area=1 |
| Sede electrónica (espublico gestiona) | https://totana.sedelectronica.es |
| Tablón de anuncios | https://totana.sedelectronica.es/board |
| Catálogo trámites | https://totana.sedelectronica.es/dossier |
| Consulta expedientes (login) | https://totana.sedelectronica.es/expedientes |
| Portal transparencia | https://totana.sedelectronica.es/transparency |
| Datos abiertos / banners | https://datos.totana.es |
| Encuentra tu sitio (SIU regional) | enlace desde datos.totana.es → capas SUBS Murcia |

## CMS y listado de expedientes

- **Web:** ASP clásico en IIS/Plesk (`*.asp`, categorías `cate=`). No hay visor urbanístico propio en la web principal; la sección `/urbanismo/` responde 403.
- **Sede:** **espublico gestiona** (Wicket). Tablón en `/board` con tabla HTML (`class_name`, `class_folderCode`, `preview-document/{uuid}`). Paginación limitada (~10 anuncios visibles).
- **Expedientes:** menú «Consulta de expedientes» (`/expedientes`) — requiere autenticación; no hay API pública de listado.
- **Transparencia:** bloque «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (~23 documentos) accesible vía portal `/transparency` (carga AJAX wicket).

## Licencias

- No hay registro histórico público de licencias otorgadas (como en otros municipios espublico).
- Edictos puntuales en tablón si el ayuntamiento publica licencias/obras (filtro por palabras clave).
- Trámites informativos: catálogo `/dossier` (respuesta lenta/intermitente desde el agente; URL documentada).
- El adapter incluye filas informativas: tablón, dossier, expedientes, transparencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM planeamiento: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs` — capa `plu_ze_37_mun_uso_suelo`, filtro `Municipio='Totana'` → **0 features** (Totana no publicada en esta capa a octubre 2026).
  - Visor regional SITMURCIA / «Encuentra tu sitio» (enlace en datos.totana.es) — consulta cartográfica, sin enlace estable expediente→polígono para scrape.
- **Estrategia:** El adapter consulta el WFS y, si en el futuro hay ámbitos `UA-*`, cruza códigos en título/expediente. Mientras tanto el orquestador geocodifica con centroide municipal (`manifest.config.centroid`) + jitter.
- **Limitaciones:**
  - Sin polígonos por expediente en fuentes abiertas.
  - Tablón y transparencia son PDFs/anuncios sin georreferencia.
  - `/dossier` con timeouts desde algunas redes; no bloquea ingesta (fuentes alternativas RSS + tablón + transparencia).
