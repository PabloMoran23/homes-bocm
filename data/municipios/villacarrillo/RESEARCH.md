# Villacarrillo — investigación portal ayuntamiento

**Municipio:** Villacarrillo (Jaén, Andalucía)  
**Slug:** `villacarrillo`  
**Boletín:** BOJA (`boja`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.villacarrillo.es | **Operativa** — WordPress + WPBakery, media en GCS (`storage.googleapis.com/stateless-www-villacarrillo-es/`) |
| Sede electrónica | https://villacarrillo.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://villacarrillo.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://villacarrillo.sedelectronica.es/dossier | Redirige a `/dossier.0`; lento/timeout en CI |
| Consulta expedientes | https://villacarrillo.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Urbanismo (WP) | Categoría `urbanismo` (id 218) vía REST API | 12 noticias (PGOU Cerro Molinos, CITI, etc.) |
| Obras y servicios | Categoría `obras-y-servicios` (id 40) | 88 noticias; filtradas por regex urbanística |
| PMVS | https://www.villacarrillo.es/plan-municipal-de-vivienda-y-suelo/ | 12 PDFs (bloques memoria/planos 2019) |
| Transparencia | https://www.villacarrillo.es/transparencia/ | Portal municipal; sin carpeta planeamiento estructurada |
| Agenda Urbana 2030 | https://www.villacarrillo.es/transparencia/agenda-urbana-2030/ | Microsite participativo |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Vera, Lepe.
- **Listado:** tabla HTML con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Descripción |
|-------|------------|-------------|
| 21/08/2026 | 2147/2026 | Consulta pública previa — Reglamento Régimen Interior CDO La Algarabía |
| 11/08/2026 | 2317/2025 | Consulta pública — Ordenanza uso y funcionamiento cementerio |
| 11/08/2026 | 2036/2026 | Anuncio obras línea 132 kV subestación Condado |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor con coordenadas.
- Trámites informativos en sede electrónica (`/dossier`, `/expedientes`).
- Las licencias concedidas publicadas aparecen en el tablón como edictos (cuando existan).
- Anuncios de tarjetas de estacionamiento para residentes en web municipal (categoría urbanismo).

## Proyectos / planeamiento

- **Tablón:** consultas públicas de ordenanzas, anuncios de obras de infraestructura.
- **Web municipal:** noticias categoría urbanismo (modificación PGOU Cerro Molinos, Proyecto Orden CITI).
- **PMVS 2019:** documentación completa en PDF (memoria, planos, fichas) en página dedicada.
- **SITUA:** visor regional Junta de Andalucía para PGOU digitalizado.
- No hay visor de seguimiento de expedientes público fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA / SituaDIFusión: `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf` — planeamiento regional digitalizado; sin WFS/REST accesible desde CI (endpoints `/geoserver/wfs` y `/rest/*` devuelven 404).
  - No hay visor urbanístico municipal propio ni datos abiertos GeoJSON.
  - PMVS y tablón publican PDFs sin georreferencia embebida.
- **Estrategia:** SITUA muestra zonificación PGOU a nivel regional, **sin campo de enlace a expediente** del ayuntamiento. Los anuncios son PDF sin coordenadas.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - `/dossier` inestable (timeout) en entorno CI.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.
- Web con media externa en Google Cloud Storage (stateless).

## Adapter implementado

- `municipio.adapters.villacarrillo:VillacarrilloAyuntamientoAdapter`
- Fuentes: tablón sede + WP REST (urbanismo/obras) + PMVS PDFs + metadato SITUA.
- IDs: `villacarrillo-lic-*` / `villacarrillo-proy-*` (sha256[:14]).
