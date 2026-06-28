# Hoyo de Manzanares — investigación portal ayuntamiento

**Municipio:** Hoyo de Manzanares (Comunidad de Madrid)  
**Fecha:** 2026-06-24  
**BOCM regional (referencia):** 23 avisos

## Resumen

Hoyo de Manzanares publica urbanismo en web corporativa WordPress (Divi) y sede electrónica eHome / espublico gestiona (Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://www.hoyodemanzanares.es/urbanismo-y-medio-ambiente/` | WordPress + PDFs | Licencias (modelos) + proyectos (guías/ordenanzas) |
| Tablón sede | `https://hoyodemanzanares.sedelectronica.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Transparencia normativa | `.../transparency/3f50e2ee-3ba3-4704-9c7b-d0ad7105c95b/` | eHome dossier | Proyectos (ordenanzas, convenios, anexos) |
| Sede trámites | `https://hoyodemanzanares.sedelectronica.es/dossier` | eHome catálogo | Informativo licencias |
| Portal transparencia | `https://hoyodemanzanares.sedelectronica.es/transparency/` | eHome | Enlaces normativos (urbanismo) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo y Medio Ambiente (WordPress)

- **URL:** `https://www.hoyodemanzanares.es/urbanismo-y-medio-ambiente/`
- **Contenido:** Modelos PDF (licencia urbanística, declaración responsable, guía paneles fotovoltaicos), enlaces a normas subsidiarias (transparencia), cartografía e inventario arbolado.
- **Licencias:** Formularios descargables; trámites electrónicos en sede.
- **Mecanismo:** Divi blurb links + `et_link_options_data` con URLs PDF.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://hoyodemanzanares.sedelectronica.es/board`
- **Formato:** Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos (jun 2026):** ordenanzas fiscales, aprobaciones BOCM, anuncios de personal (inspección urbanística).
- **Limitación:** Solo anuncios vigentes (~10 filas); paginación vía botón «Mostrar más» (Wicket AJAX, no indexable sin sesión).

### 3. Portal de transparencia — Normativa urbanística

- **URL:** `https://hoyodemanzanares.sedelectronica.es/transparency/3f50e2ee-3ba3-4704-9c7b-d0ad7105c95b/`
- **Sección:** ORDENACIÓN DEL TERRITORIO Y URBANISMO / NORMATIVA URBANÍSTICA
- **Documentos:** Convenio Canal de Isabel II (1998), ordenanzas BOCM (RCD, título habilitante, segregaciones, piscinas), anexos licencia/declaración responsable, guía fotovoltaica.

### 4. Sede electrónica — Trámites y expedientes

- **Catálogo trámites:** `/dossier` — solicitud licencia urbanística, consulta expedientes (desde 2010, requiere identificación).
- **Consulta expedientes:** `/expedientes` — requiere Cl@ve/certificado.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| ArcGIS inventario arbolado | `appid=bac2f59c9ab34a50b9b7b38dddee0742` — sin enlace a expedientes |
| IDEM visor SITCM | Cartografía regional, no expedientes municipales |
| BOCM re-parse | Ya cubierto en pipeline regional |
| `/info` sede | Redirect loop en entorno CI |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - Cartografía municipal: enlace desde urbanismo a `concejalia-de-medio-ambiente/cartografia/` (página informativa, sin WFS/ArcGIS expedientes).
  - Inventario arbolado: ArcGIS MapSeries (`appid=bac2f59c9ab34a50b9b7b38dddee0742`) — árboles, no ámbitos de expediente.
  - IDEM Comunidad de Madrid: visor cartográfico regional (`idem.madrid.org/cartografia/sitcm`).
- **Estrategia:** No hay visor urbanístico público con polígonos enlazables a expedientes/licencias. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** Tablón y transparencia solo publican PDFs/anuncios sin coordenadas ni geometría SIG.

## Estrategia de ingesta

- **proyectos.jsonl:** Dossier transparencia normativa + PDFs urbanismo + tablón sede filtrado (ordenanzas, BOCM urbanismo, convenios).
- **licencias.jsonl:** Páginas informativas (urbanismo + sede) + modelos PDF licencia/declaración responsable + tablón filtrado.
- **IDs:** `hoyo-de-manzanares-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (9+ documentos normativa + tablón + PDFs web).
- `licencias`: partial (modelos y trámites informativos; sin listado de concesiones con coordenadas).
