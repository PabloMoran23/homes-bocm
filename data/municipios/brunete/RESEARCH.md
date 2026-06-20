# Brunete — investigación portal ayuntamiento

**Municipio:** Brunete (Comunidad de Madrid)  
**Fecha:** 2026-06-20  
**BOCM regional (referencia):** 42 avisos

## Resumen

Brunete publica urbanismo en web corporativa WordPress (Divi) y sede electrónica eHome (Wicket/YUI):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://brunete.org/concejalias/urbanismo/` | WordPress + PDFs PGOU | Proyectos (planeamiento) |
| Tablón sede | `https://brunete.sedelectronica.es/board/` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Sede trámites | `https://brunete.sedelectronica.es/info` | eHome catálogo | Informativo licencias (timeout/redirect en CI) |
| Portal transparencia | `https://brunete.sedelectronica.es/transparency` | eHome | Enlaces normativos; sin dataset urbanismo |
| Geoportal SIG | `https://mun.nexusgeographics.com/brunetegp/` | Mapa interactivo Nexus | No usado (sin listado expedientes) |
| SIT Comunidad Madrid | Enlace desde urbanismo | Externo | Fuera de alcance |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://brunete.org/concejalias/urbanismo/`
- **Contenido:** PGOU aprobado 2013 (66 PDFs en `wp-content/uploads/2021/11/`: `Indice-de-Caminos.pdf`, `Cm-1.pdf` … `Cm-65.pdf`).
- **Licencias:** Página informativa sobre declaración responsable para placas solares; enlace a sede electrónica.
- **Mecanismo:** HTML estático con enlaces directos a PDF.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://brunete.sedelectronica.es/board/`
- **Formato:** Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplo urbanismo (jun 2026):** `PUBLICACION BOCM` — `ESTUDIO DE DETALLE PARCELA BA-VP-2` (exp. 4501/2024).
- **Limitación:** Solo anuncios vigentes (~10 filas); búsqueda por `?search=` no filtra en servidor (devuelve misma tabla).
- **Histórico:** No hay URL pública de archivo indexable.

### 3. Sede electrónica — Trámites y expedientes

- **Catálogo trámites:** `/info` — redirecciones múltiples desde entorno CI (no fiable).
- **Consulta expedientes:** `/expedientes` — requiere identificación Cl@ve/certificado.
- **Declaración responsable obras:** referenciada en página urbanismo (`/info.1` inestable).

### 4. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Geoportal Nexus | Mapa sin listado scrapeable |
| BOCM re-parse | Ya cubierto en pipeline regional |
| `/info` sede | Timeout/redirect en CI |

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs PGOU (urbanismo) + tablón sede filtrado (estudio de detalle, BOCM urbanismo, planeamiento).
- **licencias.jsonl:** tablón sede filtrado (licencia/obra) + página urbanismo (trámite declaración responsable).
- **IDs:** `brunete-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (66+ PDFs PGOU + anuncios tablón).
- `licencias`: partial/none (sin listado de concesiones con coordenadas; trámites informativos).
