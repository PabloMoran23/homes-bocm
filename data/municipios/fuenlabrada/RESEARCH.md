# Fuenlabrada — investigación portal ayuntamiento

**Municipio:** Fuenlabrada (Comunidad de Madrid)  
**Fecha:** 2026-06-18  
**BOCM regional (referencia):** 76 avisos

## Resumen

Fuenlabrada publica urbanismo en varios portales fragmentados:

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Sede STA (tablón) | `https://sede.fuenlabrada.es/sta/...PAGE_CODE=PTS2_TABLON` | HTML + JSON embebido (`dataset_PTS2_TABLON`) | Licencias y proyectos del tablón |
| Portal transparencia | `https://transparencia.ayto-fuenlabrada.es/ordenacion-del-territorio-y-obras/` | WordPress (Elementor) + PDFs | PGOU, modificaciones, convenios |
| Web corporativa | `https://www.ayto-fuenlabrada.es` | Liferay | Documentos PGOU (`/documents/...`) y trámites informativos |
| Geoportal | `https://geospatial.ayto-fuenlabrada.es` | Mapea/IGN | No usado (sin listado de expedientes) |

## Fuentes detalladas

### 1. Sede electrónica STA (T-Systems)

- **Base:** `https://sede.fuenlabrada.es/sta/`
- **Tablón:** `CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON`
- **Mecanismo:** Igual que Getafe — variable JS `var dataset_PTS2_TABLON = [...]` con campos `descriptionProc`, `pubDateIni`, `remitent`, `dboid`.
- **Limitación:** A junio 2026 el tablón contiene pocas entradas (incluye pruebas internas TAO). Se usa como fuente incremental cuando haya anuncios reales de urbanismo/licencias.
- **SSL:** Certificado con problemas en algunos clientes; el adapter usa `sede_insecure_ssl: true`.

### 2. Portal de transparencia — Ordenación del territorio

Sección principal de planeamiento urbanístico:

- PGOU: `/ordenacion-del-territorio-y-obras/plan-general-de-ordenacion-urbana-pgou/`
- Modificaciones PGOU: `/ordenacion-del-territorio-y-obras/modificaciones-plan-general-ordenacion-urbana/`
- Convenios urbanísticos: `/ordenacion-del-territorio-y-obras/convenios-urbanisticos/` (~70 PDFs)
- Revisión PGOU: `/ordenacion-del-territorio-y-obras/revision-del-pgouf/`

PDFs en `wp-content/uploads/` y enlaces a documentos Liferay (`ayto-fuenlabrada.es/documents/...`).

### 3. Trámites informativos (licencias)

- `/web/portal/tramites/urbanismo` — listado de trámites de urbanismo
- `/web/portal/w/licencias-de-obra-menor-en-suelo-publico` — página informativa de licencias

No hay dataset abierto de concesiones con coordenadas (a diferencia de Madrid capital).

### 4. Fuentes descartadas / bloqueadas

| Fuente | Motivo |
|--------|--------|
| `sede.ayto-fuenlabrada.es/tablon-web/bandejaAnuncios.htm` | SSL handshake falla (exit 35); tablón legacy inaccesible |
| `gobiernoabierto.ayto-fuenlabrada.es` | Timeout / inestable desde entorno CI |
| `PTS2_URBANISTICAS` en sede STA | Página no existe (404) |
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance por instrucciones |

## Estrategia de ingesta

- **proyectos.jsonl:** tablón STA (filtro urbanismo) + PDFs de transparencia (PGOU, modificaciones, convenios).
- **licencias.jsonl:** tablón STA (filtro licencia) + páginas informativas de trámites de obra.
- **IDs:** `fuenlabrada-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento` en todos los registros.

## Paridad esperada

- `proyectos`: ok (decenas de PDFs de convenios y modificaciones PGOU).
- `licencias`: partial/none (sin listado público de concesiones; solo trámites informativos).
