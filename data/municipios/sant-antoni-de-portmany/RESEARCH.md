# Sant Antoni de Portmany — investigación portal ayuntamiento

Municipio: **Sant Antoni de Portmany** (`sant-antoni-de-portmany`) — Illes Balears (Eivissa). INE 07046. Sin boletín regional asociado en cola BOCM (`bocm_count: 0`).

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (Liferay) | https://www.santantoni.net |
| Urbanismo y Actividades | https://www.santantoni.net/es_ES/ciudadania/urbanismo-y-actividades |
| PGOU (transparencia enlace) | https://www.santantoni.net/es_ES/ciudadania/urbanismo-y-actividades/plan-general-de-ordenacion-urbana |
| Avance nuevo PGOU | https://www.santantoni.net/es_ES/ciudadania/urbanismo-y-actividades/nou-pla-general-de-sant-antoni-de-portmany |
| Sede espublico gestiona | https://santantoni.sedelectronica.es |
| Tablón de anuncios | https://santantoni.sedelectronica.es/board |
| Documentos verificados PGOU (`/doc/…`) | enlazados desde la página del avance PGOU |
| Portal transparencia planeamiento | https://transparencia.santantoni.net/t/planeamiento (redirect loop desde algunos entornos) |
| MUIB (CAIB) | https://muib.caib.es/mapurbibfront/visor_index.jsp |

## Cómo se listan expedientes / planeamiento

### Avance PGOU (expediente 915/2025)

La página del **nuevo PGOU** publica tablas con títulos (memorias, normas, planos estructurales AER/APR/CS, núcleos rurales NR-*, ordenación detallada) y URLs de verificación en la sede (`https://santantoni.sedelectronica.es/doc/{token}`). Diligencia de secretaría con listado CSV en Liferay (`/documents/24432/…`).

### Tablón sede (`/board`)

HTML espublico/Wicket: filas con `class_name`, `class_folderCode`, procedimiento, categoría, fecha `DD/MM/YYYY`, enlace `preview-document/{uuid}`. En la muestra (oct–nov 2026) predominan personal, padrón y bandos; los anuncios urbanísticos son esporádicos pero el tablón es la fuente habitual de información pública de expedientes.

### Web Liferay

Sección Urbanismo describe trámites de llicències, comunicacions prèvies y autoritzacions d'activitats. No hay listado abierto de licencias concedidas con coordenadas.

### Sede — trámites

`/dossier` y `/info` pueden devolver bucles de redirección sin sesión. El catálogo del trámite participativo PGOU (`/catalog/t/c2b415d2-…`) aparece **deshabilitado** en nov 2026.

## Licencias de obra

No hay dataset público de concesiones. Fuentes:

1. **Tablón** — anuncios puntuales cuando se publican.
2. **Web** — descripción del departamento (llicències, comunicacions prèvies, activitats).
3. **Sede** — trámites telemáticos con identificación (Cl@ve / certificado).

El adapter incluye páginas informativas (tablón, urbanismo, sede) y filas del tablón filtradas por keywords urbanísticas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - **MUIB** — visor cartográfico insular (CAIB); consulta interactiva, sin API REST/WFS verificada por código de expediente municipal.
  - **Planos PGOU** en sede — PDF/planos verificables, sin geometría vectorial descargable enlazada al expediente.
  - **transparencia.santantoni.net** — portal de planeamiento (inaccesible por redirect loop en entorno cloud).
- **Estrategia:** el orquestador aplica centroide municipal + jitter (`geocode`); polígonos no extraíbles de forma determinista.
- **Limitaciones:**
  - Sin visor municipal ArcGIS/WFS público (patrón SITMUN en otros municipios baleares no verificado aquí).
  - Consulta de expedientes en sede (`/expedientes`) exige identificación.
  - `www.santantoni.net` puede devolver 403 sin User-Agent identificable.

## Limitaciones generales

- Dos dominios (`santantoni.net` corporativo, `santantoni.sedelectronica.es` operativa).
- Participación PGOU: trámite sede deshabilitado temporalmente; documentación técnica sí accesible vía `/doc/`.
- Boletín autonómico **BOIB** no indexado en cola para este municipio.
