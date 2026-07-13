# Villa del Prado — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `villa-del-prado` |
| Web municipal | https://www.villadelprado.es (Joomla + Gantry) |
| Sede electrónica | https://sede.villadelprado.es/eAdmin (add4u eAdmin) |
| Transparencia | https://transparencia.villadelprado.org (Joomla) |
| Tributos | https://tributos.villadelprado.es |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Urbanismo (transparencia) | https://transparencia.villadelprado.org/index.php/urbanismo |
| Tablón de anuncios | https://sede.villadelprado.es/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo de trámites | https://sede.villadelprado.es/eAdmin/Registrar.do?action=inicioPortalTramites |
| Carpeta ciudadano | https://sede.villadelprado.es/eAdmin/Login.do?action=login (requiere identificación) |
| Normativa subsidiaria (CCAA) | http://www.madrid.org/cartografia/planea/planeamiento/planeamiento/Villa_del_Prado/Vigente/ |

## Proyectos / planeamiento

La sección **URBANISMO** de transparencia publica documentación estática en HTML Joomla:

- **Normas subsidiarias / PGOU vigente** — enlaces a PDFs alojados en `madrid.org/cartografia/planea/.../Villa_del_Prado/Vigente/` (acuerdo, catálogo, memoria, normas, planos de ordenación)
- **Plan Especial ámbitos territoriales A, B y D suelo no urbanizable NNSS** — PDFs locales + Google Drive + BOCM-20221229-101
- **Modificación proyecto parcelación Urb. Las Hoyas** — BOCM-20230711-124 + memoria PDF
- **Plan Parcial Sector 02 La Florida** — BOCM 2026-04-13 + carpetas Google Drive (estudios, plan parcial)

Listado: HTML con enlaces `<a href="...pdf">` y carpetas Drive. No hay API JSON ni expedientes paginados.

El **tablón eAdmin** lista anuncios con título, periodo y PDF (`javascript:abrirOriginal('token')` → `ValidarDocumento.do`). En la muestra (jul 2026) predominan empleo y actas; entradas de urbanismo aparecen de forma puntual.

## Licencias de obra

- Trámites en sede eAdmin (catálogo reducido):
  - `tipoReg=5` — SOLICITUD DE COMUNICACIÓN PREVIA / PRIMERA OCUPACIÓN
  - `tipoReg=8` — Procedimiento con declaración responsable CON docu. técnica
- Presentación digital requiere certificado / Cl@ve.
- No hay listado histórico público de licencias concedidas; el tablón puede publicar edictos de licencia cuando proceda.

Estrategia adapter: filas informativas de trámites + scraping del tablón cuando haya entradas `RE_LICENCIA`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Cartografía CCAA (`madrid.org/cartografia/planea/...`) — PDFs del PGOU/normas subsidiarias, sin geometría vectorial enlazable a expedientes
  - Visor SIT Comunidad de Madrid (referenciado en otros municipios madrileños) — capas regionales sin código de expediente municipal
  - No hay visor urbanístico propio, ArcGIS, WFS ni GeoJSON en datos abiertos locales
  - Google Drive y PDFs de planeamiento sin georreferencia
- **Estrategia:** el orquestador aplicará centroide municipal + jitter vía `geocode`
- **Limitaciones:** publicaciones en PDF sin coords; tablón sin geometría; consulta de expedientes en sede requiere login

## Limitaciones generales

- CMS Joomla (web + transparencia) sin endpoint REST público para urbanismo.
- Sede eAdmin con codificación ISO-8859-1 en algunas páginas.
- Tablón con HTML de tabla; búsqueda POST por palabra clave disponible.
- Sin dataset histórico de licencias concedidas.
