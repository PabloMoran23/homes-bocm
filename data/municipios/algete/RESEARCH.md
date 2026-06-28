# Algete — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `algete` |
| Web municipal | https://www.aytoalgete.es (Joomla) |
| Sede electrónica | https://algete.sedelectronica.es (espublico gestiona / eHome) |
| Transparencia | https://transparenciaalgete.eadministracion.es/portal |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Urbanismo | https://www.aytoalgete.es/index.php?Itemid=519&id=111&option=com_content&view=article |
| PGOU / planeamiento | https://www.aytoalgete.es/index.php?Itemid=654&id=192&option=com_content&view=article |
| Tablón de anuncios | https://algete.sedelectronica.es/board/ |
| Consulta expedientes | https://algete.sedelectronica.es/expedientes |
| Trámites urbanismo (sede) | https://algete.sedelectronica.es (catálogo; requiere identificación) |

## Proyectos / planeamiento

La concejalía publica documentación en la página **Urbanismo** (Joomla `com_content`):

- **Avance planeamiento sector Algete Norte** — tomos I–V, decretos, publicaciones IP/BOCM en `/images/DOCUMENTACION/AlgeteNorte/`
- **Plan Especial Espino 1** — aprobación definitiva, certificados, BOCM
- **Plan Especial Locales Comerciales** — `/images/DOCUMENTACION/2026/`
- **Expropiación sector 10** — edictos y certificados en `/images/Urbanismo/`
- **Modificaciones puntuales** — p. ej. `AU_Algete_30ene2025.pdf`, `20250321_MP1_PPRI_APR1`

Listado: HTML estático con enlaces `<a href="...pdf">`. No hay API JSON ni listado paginado de expedientes urbanísticos.

El **PGOU vigente** se consulta vía el visor regional SIT-CM (enlace desde la página de planeamiento), no como expedientes individuales en el portal municipal.

## Licencias de obra

- Formularios y guías de trámites en la página Urbanismo (declaración responsable, obra mayor, calas, LPO, placas solares).
- Presentación digital en sede electrónica (requiere certificado / Cl@ve).
- El **tablón de anuncios** puede publicar licencias/concesiones cuando proceda; en la muestra consultada (jun 2026) solo aparecían convenios/subvenciones, sin filas de urbanismo.

Estrategia adapter: filas informativas de trámites + scraping del tablón cuando haya entradas `RE_LICENCIA`.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Visor SIT Comunidad de Madrid: http://idem.madrid.org/cartografia/sitcm/html/visor.htm (PGOU regional, sin código de expediente municipal enlazable)
  - SIGMA `PLANEAMIENTO_URBANISTICO` MapServer: capas de ámbitos sin campo municipio/expediente utilizable para cruzar con filas del portal
  - No hay visor urbanístico propio del ayuntamiento ni WFS/GeoJSON en datos abiertos locales
- **Estrategia:** el orquestador aplicará centroide municipal + jitter vía `geocode`
- **Limitaciones:** publicaciones en PDF sin georreferencia; tablón sin geometría; consulta de expedientes en sede requiere login

## Limitaciones generales

- CMS Joomla sin endpoint REST público para urbanismo.
- Tablón eHome con HTML de tabla; paginación posible en otros momentos.
- Sin listado público histórico de licencias concedidas (solo trámites y tablón puntual).
