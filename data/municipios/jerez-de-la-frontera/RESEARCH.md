# Jerez de la Frontera — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `jerez-de-la-frontera` |
| Web corporativa | https://www.jerez.es (TYPO3 CMS) |
| Sede electrónica | https://www.sedeelectronica.jerez.es |
| Tablón edictos | https://tramites.aytojerez.es/public/general/tablon-anuncios |
| API tablón | `GET https://tramites.aytojerez.es/api/tablon-anuncios` (+ detalle `/{idExpediente}`) |
| Urbanismo (web) | https://www.jerez.es/webs-municipales/urbanismo |
| Transparencia urbanismo | https://transparencia.jerez.es/infopublica/varios/urbanistica |
| Boletín | BOJA (`boletin_source_id: boja`) |

## Fuentes de proyectos / expedientes

### 1. Tablón de anuncios (API REST)

SPA Vue en `tramites.aytojerez.es` con API JSON pública:

- **Listado:** `GET /api/tablon-anuncios` → `{ isOk, datos: [{ idExpediente, extracto, fechaExposicion, entidad, ... }] }`
- **Detalle:** `GET /api/tablon-anuncios/{idExpediente}` → `{ edicto, documentos[] }`
- Fechas en formato `DD-MM-YYYY`
- ~33 edictos activos; ~5-7 de Delegación de Urbanismo o con keywords urbanísticas
- Documentos descargables vía token en detalle (no necesario para metadatos)

### 2. TYPO3 — instrumentos de planeamiento (PDFs + títulos H3)

Secciones semilla en `jerez.es/webs-municipales/urbanismo/`:

| Sección | URL |
|---------|-----|
| En fase de información | `/instrumentos-de-planeamiento/instrumentos-de-planeamiento-en-fase-de-informacion` |
| Planeamiento general | `.../planeamiento-general` |
| Planes parciales | `.../planes-parciales` |
| Planes especiales | `.../planes-especiales` |
| Estudios de detalle | `.../estudios-de-detalle` |
| PGOU refundido | `/webs-municipales/urbanismo/pgou` |
| Convenios urbanísticos | `/info-publica/convenios-urbanisticos` |
| Bandos | `/info-publica/bandos` |

PDFs en `/fileadmin/Documentos/urbanismo/Anuncios/Planeamiento/` (PTOEO, PTOPRI, PTOED, PEER, POU, BOP/BOJA).

Títulos de instrumentos en `<h3>` (aprox. 50+ actuaciones vigentes/en trámite).

### 3. Noticias urbanismo (TYPO3)

Feed de noticias en `/webs-municipales/urbanismo/evento-simple-noticias-urbanismo/*` con licencias concedidas y actuaciones (complementario).

## Licencias

**No hay dataset histórico público de concesiones** (como Madrid o Dipusevilla).

Fuentes disponibles:

1. **Sede electrónica — catálogo urbanismo** (~49 trámites informativos):
   `https://www.sedeelectronica.jerez.es/tramites?tema=Urbanismo&...listurbanismo`
   Ej.: `licencia_de_obra_mayor`, `declaracion-obra-simplificada`, `licencia_de_obras_menor`, etc.

2. **Tablón** — edictos puntuales de licencias publicadas (ej. «LICENCIA PARA ADECUACIÓN Y AMPLIACIÓN...»).

3. **Noticias urbanismo** — comunicados de licencias concedidas (sin API; crawl opcional).

Estrategia adapter: páginas informativas de trámites sede + edictos tablón con keyword licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - `callejero.jerez.es` — callejero turístico propietario (no planeamiento ni expedientes)
  - Web urbanismo — solo PDFs/CAD estáticos en `/fileadmin/`, sin visor ArcGIS/WFS
  - Búsqueda en jerez.es — sin visor urbanístico público
  - SITUA Junta de Andalucía — sin capa WFS enlazable por expediente para Jerez
  - Diputación de Cádiz — sin WFS municipal de sectores para Jerez detectado
- **Estrategia:** orquestador aplicará centroide municipio + jitter vía geocode
- **Limitaciones:** documentación cartográfica solo en PDF; sin API GIS pública

## Limitaciones

- Tablón API devuelve solo edictos **activos** (~33); histórico completo no expuesto
- TYPO3 sin REST API; crawl HTML de páginas semilla
- Sede tramites: páginas informativas, no listado de concesiones
- Sin geometría de ámbito en portal público
