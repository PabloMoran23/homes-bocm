# Aznalcázar — investigación portal ayuntamiento

Municipio: **Aznalcázar** (`aznalcazar`) — Sevilla, Andalucía  
INE: **41012** | Boletín: **BOJA** (1 aviso histórico)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (OpenCMS INPRO) | https://www.aznalcazar.es/es/ |
| Delegación Urbanismo | https://www.aznalcazar.es/es/ayuntamiento/delegaciones/detalle/Urbanismo-00034/ |
| Noticias categoría Urbanismo | https://www.aznalcazar.es/es/busqueda/?formCategoryFilter=/sites/aznalcazar/.categories/temas/Urbanismo/&formTypeFilter=pm-noticia |
| Participa / PREPU (PGOM) | https://www.aznalcazar.es/es/ayuntamiento/prepu/ |
| Normativa municipal | https://www.aznalcazar.es/es/ayuntamiento/normativa-municipal |
| Tablón web (redirect) | https://www.aznalcazar.es/.galleries/enlaces-servicios/etablon → sede |
| Sede espublico gestiona | https://aznalcazar.sedelectronica.es |
| Tablón sede | https://aznalcazar.sedelectronica.es/board/ |
| Transparencia sede | https://aznalcazar.sedelectronica.es/transparency |
| Trámites (dossier) | https://aznalcazar.sedelectronica.es/dossier |
| LicytalPub Dip. Sevilla | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4101200A |
| Tablón INPRO Dip. Sevilla | https://portal.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41012 |
| SITUA (Junta Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## CMS y listado de expedientes

- **Web:** OpenCMS INPRO (`es.inpro.opencms.*`). Noticias por categoría `/sites/aznalcazar/.categories/temas/Urbanismo/`. PDFs en `/export/sites/aznalcazar/.galleries/`.
- **Sede:** espublico gestiona (Wicket). Tablón `/board/` con filas HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_dateFrom`). ~10 filas visibles; en la revisión no había edictos de urbanismo recientes.
- **Transparencia sede:** sección AJAX **09.- Urbanismo y Medio Ambiente** (documentos no scrapeables sin sesión Wicket).
- **Tablón Diputación Sevilla:** INPRO en `portal.dipusevilla.es` con INE 41012; formulario de búsqueda POST (sin listado precargado en GET; requiere interacción).
- **Licencias concedidas:** portal provincial **LicytalPub** (CIF `P4101200A`); no hay dataset descargable en web municipal.

## Licencias de obra

- No hay listado histórico público en sede municipal (solo tablón de edictos recientes).
- Trámites informativos vía `/dossier` y consulta provincial LicytalPub.
- El adapter incluye filas informativas (tablón sede, trámites, LicytalPub, tablón Diputación) siguiendo patrón Tomares/Lepe.

## Proyectos / planeamiento

- **PGOM en tramitación:** noticia *CONVOCATORIA: AVANCE DEL PGOM AZNALCÁZAR* (30/04/2026).
- **PREPU:** PDFs de documentación gráfica y memoria descriptiva (28/01/2022) en `/es/ayuntamiento/prepu/`.
- Noticias urbanismo: VPO, registro demandantes vivienda, etc. (filtradas por categoría + regex urbanística).
- Referencia SITUA para planeamiento general (sin geometría descargable por API).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** sin visor urbanístico municipal; página información catastral sin enlace ArcGIS/WFS; SITUA/VITUA Junta (JSF, sin WFS por código de expediente); transparencia sede con docs PDF sin georreferencia.
- **Estrategia:** orquestador aplicará centroide municipal `[37.3044, -6.2714]` + jitter vía `geocode`.
- **Limitaciones:** certificado SSL inválido en `www.aznalcazar.es` (adapter usa `insecure_ssl`); tablón Diputación requiere POST interactivo; transparencia sede vía AJAX Wicket.

## Limitaciones generales

- Tablón sede muestra solo anuncios recientes (~10); histórico en Diputación INPRO no automatizable sin búsqueda.
- Normativa municipal enlaza a `/normative` (redirige a error 404).
- Consulta expedientes sede requiere autenticación.
