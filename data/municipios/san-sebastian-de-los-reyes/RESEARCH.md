# San Sebastián de los Reyes — investigación portal ayuntamiento

**Fecha:** 2026-06-21  
**Slug:** `san-sebastian-de-los-reyes`  
**BOCM regional (referencia):** 38 avisos

## Resumen

El ayuntamiento publica urbanismo en un **portal Liferay** (`www.ssreyes.org`) con sede electrónica
en `sede.ssreyes.es` y transparencia en `transparencia.ssreyes.org`.

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.ssreyes.org | Liferay 7.x | PGOU, normativa, planes, modificaciones, acuerdos comisión PGOU |
| Sede electrónica | https://sede.ssreyes.es | Liferay | Tablón edictos/anuncios (IQRS), trámites licencia, actas pleno |
| Transparencia | https://transparencia.ssreyes.org | Liferay | Información urbanística, convenios |

## Protección anti-bot

La web principal y la sede muestran una página intermedia *«Verificando navegador…»* que establece
la cookie `browser_verified=1`. Sin ella, el scraping recibe HTML vacío (1847 bytes). El adapter
envía esa cookie en todas las peticiones.

## Fuentes de proyectos / expedientes

### 1. Documentos Liferay (`/documents/...`)

Páginas semilla con PDFs de planeamiento:

- **Normativa urbanística:** `/normativa-urban%C3%ADstica` (14 PDFs PGOU: normas suelo, zonas, anexos)
- **Acuerdos comisión PGOU:** `/acuerdos-de-la-comisi%C3%B3n-t%C3%A9cnica-de-seguimiento-del-pgou` (25 PDFs)
- **Avance-revisión PGOU:** `/avance-revisi%C3%B3n-plan-general` (4 PDFs)
- **Planos:** `/planos` (3 PDFs)
- **Aprobaciones/modificaciones:** páginas de plan especial, 9ª modificación puntual Z.O. 59, etc.
- **Desarrollo urbano:** `/es/desarrollo-urbano`, `/nuevos-desarrollos-urban%C3%ADsticos`

Formato HTML: enlaces con `class="document document-pdf"` y atributo `title="..."`.

### 2. Transparencia — información urbanística

- https://transparencia.ssreyes.org/informaci%C3%93n-urban%C3%8Dstica-y-medioambiental
- Enlaces cruzados a PGOU y desarrollos en web principal.

### 3. Tablón de anuncios (limitado)

- Web: `/es/tabl%C3%B3n-de-anuncios-y-edictos` — solo enlace a Excel estadístico (conteos 2017–2023).
- Sede: `/tabl%C3%B3n-de-edictos-y-anuncios` → `/sedeFormsNoClave/ReturnPage?metodo=IQRS`
- **IQRS requiere autenticación Cl@ve** — listado de anuncios individuales no scrapeable sin login.

## Fuentes de licencias

**No hay dataset público de concesiones** con coordenadas (sin paridad Madrid capital).

Fuentes disponibles:

1. **Páginas informativas:** `/es/licencias-de-actividad`, `/es/obras-e-infraestructuras`
2. **Trámites sede (autoliquidación):** `sedeForms/IndexPage?metodo=LIQUI_LicenciaObra`,
   `LIQUI_LicenciaActividad`, `LIQUI_LicenciaVeladores`, `LIQUI_OcupacionVia`
   (páginas de trámite, no concesiones publicadas)
3. Tablón IQRS bloqueado por Cl@ve (ver arriba).

## Limitaciones

- Cookie `browser_verified=1` obligatoria en www y sede.
- Tablón electrónico IQRS inaccesible sin Cl@ve; Excel del tablón solo tiene estadísticas agregadas.
- Sin geolocalización en fuentes del ayuntamiento (`lat`/`lon` = null).
- Algunos PDFs de sede usan host interno `intranet.ssreyes.local` (no accesibles externamente).
- No replicar pipeline Madrid capital (`sector_geometry/madrid_*`).

## Estrategia de ingesta

- **proyectos.jsonl:** crawl determinista de páginas semilla urbanismo + extracción `/documents/` con título.
- **licencias.jsonl:** páginas informativas de trámites + sede LIQUI_* (paridad informativa, `min_rows: 0`).
- **IDs:** `ssreyes-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.
