# Altea — investigación portal ayuntamiento

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal | https://altea.es |
| API contenidos (Digital Value) | https://api.digitalvalue.es/contents/altea/collections |
| Área urbanismo | https://altea.es/areas/urbanismo |
| Sede electrónica | https://altea.sedelectronica.es |
| Tablón de anuncios | https://altea.sedelectronica.es/board |
| Trámites urbanismo | https://altea.es/areas/urbanismo/tramites |

## CMS / tecnología

- **Plataforma:** Digital Value (Zity) — SPA Mithril + Leaflet.
- **Contenidos:** colección `articulos` en API REST (`limit`/`offset`).
- **Sede:** espublico gestiona (Wicket), certificado SSL con cadena incompleta en algunos entornos (`insecure_ssl: true`).

## Proyectos / planeamiento

### Fuentes identificadas

1. **API `articulos`** — ~445 entradas; filtro por título/slug/categoría `urbanismo`:
   - Sectores urbanísticos (SECTOR ALHAMA, SECTOR LA OLLA, RS-8 BBAA, etc.) con `filesGroup` (PDFs DOCV/BOP).
   - Modificaciones PGOU (cementerio, sector B, zonas 10E/4, VUT).
   - PGE/PGOU: Plan General Estructural 2026, versión definitiva PGE 2023, propuesta PGE 2019.
   - Información pública: saneamiento Galera Palmeres, rehabilitación costera, LSMT Bellas Artes.
   - Documentos en tramitación: PAI Sanchuchim + reparcelación (PDFs en `filesGroup`).

2. **Tablón sede** (`/board`) — edictos recientes filtrados por urbanismo/licencias (primera página HTML).

### Cómo se listan

- Artículos con metadatos JSON (`title`, `data.slug`, `filesGroup`, `date`).
- Sin listado tabular de expedientes con código único; sectores como páginas individuales con PDFs adjuntos.
- Hub pages vacíos en API (`Documentos de Planeamiento`, `Proyectos en Desarrollo`) — contenido en hijos vía menú.

## Licencias

### Fuentes

1. **Trámites urbanismo** (artículo API `68133cb60c2bd4518f7f5af8`) — `tablesGroup` con 16 procedimientos:
   - Licencia edificación, demolición, urbanización, parcelación, grúa, DR obras, certificados urbanísticos.
   - URLs: `https://altea.sedelectronica.es/catalog/t/{uuid}`

2. **Tablón sede** — edictos de licencias/urbanismo cuando aparecen (sin histórico completo público).

### Limitaciones

- No hay dataset público de licencias concedidas con coordenadas.
- Solo fichas procedimentales + edictos puntuales en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Mapa interactivo IVT (vivienda turística) en artículo ordenanza PGOU 4-8 — Leaflet embebido en SPA, sin API ArcGIS/WFS pública consultable por expediente.
  - PDFs de zonificación IVT en `filesGroup` del artículo VUT (`Pla_01_AMBITOS`, `Pla_02_Z_VULNERABLES`, `Pla_03_Z_IPRE`).
  - Visor DPMT Ministerio (enlace externo en información de interés): http://sig.mapama.es/dpmt/visor.html
  - Sectores urbanísticos: solo planos PDF, sin GeoJSON/WFS municipal.
- **Estrategia:** No hay query determinista expediente→polígono. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** Mapa IVT requiere JavaScript; polígonos no expuestos vía REST. Sin visor urbanístico ArcGIS municipal tipo Madrid/Getafe.

## Limitaciones generales

- SPA sin HTML server-side en rutas `/articulos/*` (solo shell JS).
- Sede electrónica: SSL intermitente; tablón paginado con Wicket (solo primera página sin sesión).
- Boletín regional: DOGV (`boletin_source_id: dogv`), 7 entradas BOCM ya en pipeline central.
