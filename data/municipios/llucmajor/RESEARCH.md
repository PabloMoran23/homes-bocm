# Llucmajor — investigación portal ayuntamiento

Municipio: **Llucmajor** (`llucmajor`) — Illes Balears, Mallorca. INE **07027**. Sin boletín regional asociado en cola.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 10) | https://llucmajor.org |
| Urbanisme i cadastre PIC | https://llucmajor.org/ca/urbanismecadastre-pic |
| Tràmits àrea Urbanisme | https://llucmajor.org/ca/tramits_areas/Urbanisme |
| Enllaços urbanisme (ordenances) | https://llucmajor.org/ca/enlla%C3%A7os/enllacos-area-urbanisme |
| Anuncis | https://llucmajor.org/ca/anuncis |
| Sede electrónica (espublico) | https://llucmajor.sedelectronica.es |
| IDE IDELMA municipal | https://ide.idelma.cat/ide_llucmajor |
| Visor MUIB (CAIB) | https://muib.caib.es/mapurbibfront/visor_index.jsp |
| Arxiu urbanístic CIM | https://ide.conselldemallorca.cat/visor/arxurb/ |
| Normativa MUIB per municipi | http://muib.caib.es/mapurbibfront/normativa_triar_pla.jsp?municipi=Llucmajor |

## Cómo se listan expedientes

### Web Drupal

- **Urbanisme PIC:** página informativa con enlaces a visores (IDELMA, MUIB, arxurb), PDFs (p. ej. acuerdo DA7 legalización extraordinaria 2025, guía EPCU) y correo `urbanisme@llucmajor.org`.
- **Enllaços àrea urbanisme:** nodos tipo «enllaç» con textos de ordenanzas (residuos construcción, instalaciones, etc.) y PDF BOIB enlazados.
- **Tràmits:** fichas Drupal bajo `/ca/tramits/…` (licencia obra mayor, comunicación previa, certificados, etc.) — contenido procedimental, no listado de concesiones.
- **Anuncis:** listado editorial; pocos avisos urbanísticos estructurados.

No hay sección equivalente a «expedientes en información pública» con slugs por proyecto (cf. Pozuelo) ni JSON:API público (`/jsonapi` → 404).

### Sede espublico

`/board`, `/catalog` y hosts alternativos (`ajllucmajor`, `llucmajor-tramits`) devuelven HTML **«Sede Electrónica Indeterminada»** sin filas de tablón (`class_name`). No usable para scrape determinista en oct-2026.

### GIS / planeamiento

- **IDELMA M027:** workspaces `M027_Annex1_*`, `M027_CAMINS`, `M027_Inca` (límites/núcleos), `M027_MEDI_AMBIENT` — **no** hay `M027_URBANISME` ni capa `exp_absis` como en Pollença (M042).
- **MUIB / arxurb:** consulta normativa y documentación; no API de expedientes con geometría enlazable por código.

## Licencias de obra

No hay dataset abierto de licencias concedidas. Fuentes implementadas:

1. Páginas de trámite Drupal (obra mayor, prórrogas, DR, certificados, ocupación vía pública, etc.).
2. Sede/tablon: no operativo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - IDELMA `ide_llucmajor` / WFS global — sin capa expedientes urbanísticos M027
  - MUIB `visor_index.jsp` — planeamiento normativo, sin join a expediente municipal
  - `ide.conselldemallorca.cat/visor/arxurb/` — archivo documental
- **Estrategia:** el orquestador usará centroide municipal + jitter (`geocode`)
- **Limitaciones:** sin polígonos por expediente/licencia; visores sin WFS de actuaciones; sede sin tablón

## Limitaciones generales

- Dominio principal `llucmajor.org` (CloudFront + Drupal).
- Sede espublico mal configurada o no vinculada al municipio en este entorno.
- Contenido de planeamiento disperso (PDFs, ordenanzas, visores externos).
- Contacto: urbanisme@llucmajor.org
