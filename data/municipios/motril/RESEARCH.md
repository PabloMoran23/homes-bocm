# Motril — investigación portal ayuntamiento

Municipio: **Motril** (`motril`), provincia Granada, Andalucía. Sin entradas BOCM/BOJA en el histórico del pipeline (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://motril.es | WordPress (Yoast) |
| Urbanismo — información pública | https://motril.es/urbanismo/informacion-publica/ | PDFs IP, resoluciones, estudios |
| Consulta pública | https://motril.es/urbanismo/consulta-publica/ | PDFs consultas |
| Planeamiento / PGOU | https://motril.es/urbanismo/planeamiento/ | Índice PGOU, planos por núcleo |
| Modificaciones PGOU | https://motril.es/urbanismo/plan-general-de-ordenacion-urbanistica/modificaciones/ | Enlaces normativa |
| Sede electrónica | https://sede.motril.es | STA T-Systems |
| Tablón IP urbanismo | `sede…/PTS2_TABLON&KEY=3223500033794117807831` | Dataset JS embebido `dataset_PTS2_TABLON` |
| Tablón general | `sede…/PTS2_TABLON&KEY=all` | ~66 anuncios (filtrar urbanismo) |
| Catálogo trámites | `sede…/PAGE_CODE=PTS_CATSERV` | `dataset_CATSERV` (~402 trámites) |
| Transparencia | https://transparencia.motril.es | Portal separado (JGL, comisiones) |
| Obra menor (info) | https://motril.es/solicitud-obra-menor/ | Página informativa |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18087 | Planeamiento digitalizado Junta (INE 18087) |

## Expedientes / proyectos

1. **WordPress:** La sección *Información pública* publica acuerdos, memorias, planos y resoluciones de expedientes urbanísticos como PDF en `wp-content/uploads/` (fechas en ruta `…/2024/01/…`). *Consulta pública* y *modificaciones PGOU* aportan documentación complementaria.
2. **Sede STA:** El tablón `PTS2_TABLON` expone filas con `descriptionProc`, `externString` (nº expediente), `pubDateIni` y `dboid`. Detalle vía `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`. Respuesta lenta (~30–120 s); requiere timeout amplio.
3. **Catálogo PTS_CATSERV:** Trámites de urbanismo (planes parciales, reparcelación, certificados urbanísticos, declaraciones responsables de obra, etc.) — páginas informativas, no listado de expedientes abiertos.
4. **SITUA:** Visor regional de instrumentos de planeamiento aprobados (raster); no API por código de expediente municipal.

## Licencias de obra

- **Sin dataset histórico** de licencias concedidas en web abierta (no hay página tipo «licencias concedidas»).
- Tablón STA puede incluir anuncios de licencias/obras cuando se publican; filtro por palabras clave en adapter.
- Catálogo sede: trámites de licencia, comunicación previa y declaración responsable (informativos).
- Página *Solicitud obra menor* — acceso a trámite, no registro público.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Planos PGOU en motril.es (`…/planos/…`): PDFs cartográficos por núcleo (Motril, Carchuna, Calahonda, etc.), sin servicio WMS/WFS público.
  - VITUA (Junta de Andalucía): visor autonómico Mapea; consulta por municipio, sin enlace a expediente del ayuntamiento ni geometría vectorial descargable por código.
  - SITUA cid=18087: documentación escaneada, sin GetFeature por expediente.
  - Sede STA: sin capa GIS ni coordenadas en dataset tablón.
  - transparencia.motril.es: sin visor urbanístico identificado.
- **Estrategia:** No aplicable; orquestador usará centroide manifest + jitter.
- **Limitaciones:** PDFs sin georreferencia vectorial; sede lenta; sin ArcGIS REST municipal.

## Limitaciones técnicas

- `sede.motril.es` (T-Systems STA) responde con latencia alta; usar `fetch_timeout_s: 120`.
- Tablón `KEY=urbanismo` y `KEY=all` se fusionan en adapter (dedupe por `dboid`).
- Scrape determinista: regex PDF en WP + parse JSON embebido en HTML STA.
- Sin listado machine-readable de licencias concedidas.
