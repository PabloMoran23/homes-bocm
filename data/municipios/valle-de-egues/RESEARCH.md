# Valle de Egüés / Eguesibar — investigación portal

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sedeelectronica.valledeegues.es/ | Plataforma **Sedipualba** (Informática Diputación Albacete): catálogo, carpeta ciudadana, tablón |
| Catálogo urbanismo | https://sedeelectronica.valledeegues.es/catalogoservicios.aspx?area=146&ambito=16 | Trámites LICENCIA de obras, declaración responsable, primera utilización, etc. |
| Tablón anuncios | https://sedeelectronica.valledeegues.es/tablondeanuncios/ | Listado HTML + **RSS** (`tablon_rss.aspx`) |
| Web ayuntamiento | https://www.valledeegues.com/ | WordPress; sección PGM |
| PGM / EOT | https://www.valledeegues.com/plan-general-municipal-del-valle-de-egues-estrategia-y-modelo-de-ocupacion-territorial/ | Documentación Estrategia y Modelo de Ocupación Territorial |
| SIUN Navarra | https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html | Consulta instrumentos de planeamiento (enlace desde IDENA) |
| Geoportal IDENA | https://geoportal.navarra.es/es/visores | Visor SITNA / capas INFOTU |

## Listado de expedientes / anuncios

- **Tablón:** tabla ASP.NET en `tablondeanuncios/default.aspx`; títulos en celda + enlace `anuncio.aspx?id=`. RSS con ~10 últimos anuncios (encoding ISO-8859-1).
- **Categorías tablón:** Acuerdos, Bando, Convocatorias, Edictos, Empleo, Otras AAPP, Otros (sin categoría «Urbanismo» dedicada).
- **Ejemplos urbanísticos en tablón:** bandos de aprobación inicial de modificaciones pormenorizadas (p. ej. parcela/polígono en Ardanaz); edictos ISIVTNU/plusvalía.
- **Licencias:** no hay listado público de concesiones; solo fichas informativas de trámites en catálogo (`carpetaciudadana/tramite.aspx?idtramite=…`).
- **SEGEX:** trámite «Sistema Electrónico de Gestión de Expedientes» en catálogo general; consulta de expedientes requiere identificación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDENA `IDENA:INFOTU_Pol_PlanUrbMun` — polígono del **planeamiento municipal vigente** del término (filtro `MUNICIPIO ILIKE '%Eg%es%'` → «Valle de Egüés / Eguesibar», CMUNICIPIO 86).
  - Propiedades: `URLSIUN`, `INSTRUMENT`, `URLBON`.
  - Geoportal Navarra / visores IDENA para consulta cartográfica general (sin enlace directo expediente↔geometría en tablón).
- **Estrategia adapter:** polígono WFS en fila de planeamiento municipal (origen `idena_wfs`) y semillas web PGM/visor; anuncios del tablón **sin** polígono por expediente (solo metadatos + URL).
- **Limitaciones:** modificaciones pormenorizadas y licencias en tablón/PDF sin capa WFS enlazable por código de expediente; SIUN/SEGEX no scrapeables sin login.
