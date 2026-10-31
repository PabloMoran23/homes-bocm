# Xàtiva — investigación portal ayuntamiento

Municipio: **Xàtiva** (`xativa`) — Valencia, Comunitat Valenciana. INE `46245`. Sin boletín regional asociado en cola.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.xativa.es/ |
| Urbanismo | https://www.xativa.es/es/urbanismo/pagina/urbanismo |
| PGOU | https://www.xativa.es/es/urbanismo/pagina/pgou-xativa-plan-general-ordenacion-urbana |
| Sede electrónica (espublico gestiona) | https://xativa.sedelectronica.es/ |
| Tablón de anuncios | https://xativa.sedelectronica.es/board |
| Catálogo trámites | https://xativa.sedelectronica.es/dossier |
| Transparencia (sección 8 urbanismo, 25 docs) | https://xativa.sedelectronica.es/transparency — enlace vía menú Wicket AJAX |
| Visor gvSIG Online | https://xativa.gvsigonline.com/gvsigonline/core/load_public_project/Urbanismo/ |
| ICV GVA visor | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion |

## Expedientes / planeamiento

- **Tablón `/board`:** tabla HTML Wicket (espublico gestiona) con columnas Documento, Expedient, Procediment, Categoria, Descripció, Data. Categoría **Urbanisme** con procedimientos *Planejament General* y *Planejament de Desenvolupament* (p. ej. modificación puntual PGOU exp. 6711/2025, estudio detalle sector R-6 Pereres exp. 15096/2023). Enlaces `preview-document/{uuid}`.
- **Web municipal:** página PGOU y urbanismo con descripción del SIG (informe por parcela, normativa PGOU). Sin listado scrapeable de expedientes en trámite fuera del tablón.
- **Transparencia sede:** sección 8 «URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» (25 documentos); carga por AJAX Wicket — no incluida en adapter v1.
- **Consulta expedientes:** carpeta electrónica en sede; requiere identificación con certificado.

## Licencias

- No hay dataset público de licencias concedidas con dirección/coordenadas.
- Trámites de obra vía sede (`/dossier`, ~140 trámites); solicitud con certificado electrónico.
- El tablón puede publicar edictos urbanísticos puntuales; en la muestra reciente predominan planeamiento sobre licencias de obra.
- Adapter incluye filas informativas: tablón, dossier y página urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **gvSIG Online:** proyecto público «Urbanismo» (`xativa.gvsigonline.com`) — consulta parcelas, PGOU, conjunto histórico; sin API REST documentada para enlace expediente→polígono en scrape batch.
  - **ICV GVA WFS:** `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, filtro client-side `cod_ine_mun=46245`. Paginación `startIndex` 0–12000. GML3 → GeoJSON WGS84.
  - **Visor GVA:** capa zonificación CV (referencia regional).
- **Estrategia:** instrumentos GVA como filas base (`gva_wfs`) con polígono; enriquecimiento tablón/PGOU por keywords (Pereres, PGOU, sector, industrial); filas visor/PGOU web con geometría cuando coincide zonificación ICV.
- **Limitaciones:** zonificación agregada por instrumento, no ámbito exacto de cada expediente municipal; gvSIG requiere sesión JS; tablón solo primera página sin paginación Wicket.

## Limitaciones generales

- Sede espublico: SSL válido; `insecure_ssl: true` por consistencia con otros adapters espublico.
- WFS ICV: descarga paginada lenta (~2–3 min en CI); timeouts mitigados con reintentos.
- Sin re-parse BOCM en este adapter (`bocm_count: 0`).
