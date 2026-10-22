# Manresa — investigación portal ayuntamiento

**Slug:** `manresa`  
**Comunidad:** Catalunya (Barcelona)  
**Web oficial:** https://web.manresa.cat (redirige desde www.manresa.cat)

## Fuentes localizadas

| Área | URL | Formato |
|------|-----|---------|
| Urbanisme (menú) | https://web.manresa.cat/web/menu/632-urbanisme | HTML CMS propio |
| Planejament en tràmit | https://web.manresa.cat/web/article/1804-planejament-en-tramit | Listado → sub-artículos `/web/article/.../ID` |
| Planejament vigent | https://web.manresa.cat/web/article/3684-planejament-vigent | Artículo + enlaces |
| Plans especials | https://web.manresa.cat/web/article/2349-plans-especials | ~70 sub-artículos |
| Convenis urbanístics | https://web.manresa.cat/web/article/3074-convenis-urbanistics | Sub-artículos |
| Tràmits urbanisme | https://web.manresa.cat/web/menu/632-urbanisme/tramits | Tabla HTML → `/seu/menu/fitxa/{id}` |
| Seu electrònica | https://www.manresa.cat/seuelectronica | Materialize + Kendo |
| Tauler d'anuncis | https://www.manresa.cat/etauler | e-TAULER (React SPA, sin dataset en HTML) |
| Dades obertes | https://www.seu-e.cat/ca/web/manresa/dades-obertes | Portal transparencia CCAA |
| Descàrrega cartografia | https://www.manresa.cat/seuelectronica/menu/13118 | Página informativa (sin WFS directo en scrape) |
| Plànol guia | http://web.manresa.cat/microsites/visor_guia/index_proj.html | Visor turístico, no expedientes |

## Cómo se listan expedientes / proyectos

- El ayuntamiento usa un **CMS PHP propio** (`web.manresa.cat`): cada instrumento o fase de planeamiento es un **artículo** con `<h1>` y PDFs en `/media/docs/arxius/`.
- Los índices (`planejament-en-tramit`, `convenis`, `plans-especials`) enlazan a URLs del tipo  
  `https://web.manresa.cat/web/article/{parent-slug}/{numeric_id}`.
- Fechas inferibles de nombres de PDF (`YY-MM-DD_anunci`, `dilig_pou_...`) o texto del cuerpo.
- No hay API JSON pública ni sitemap de expedientes; el adapter recorre las semillas configuradas.

## Licencias de obra

- **No** hay tablón público scrapeable de concesiones (e-TAULER requiere SPA/API no expuesta en HTML estático).
- La sede publica **fichas de trámite** enlazadas desde urbanisme/tramits (`/seu/menu/fitxa/132` llicència d'edificació, etc.).
- El adapter ingiere esas fichas como filas informativas (`fecha_concesion: null`), patrón Pozuelo/Tarragona.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** Plànol guia (microsite turístico), menú «Descàrrega de cartografia» (sin REST/WFS enlazado a códigos de expediente), e-TAULER, datos abiertos seu-e (sin capa urbanística con join por expediente).
- **Estrategia:** El orquestador usará centroide municipal (`manifest.portal.config.centroid`) + jitter vía geocode.
- **Limitaciones:** Instrumentos publicados como PDF sin georreferencia; no hay visor ArcGIS/GeoServer con campo expediente accesible sin autenticación.

## Limitaciones técnicas

- `request_delay_s` recomendado ≥ 0.35 s (Apache/nginx en web.manresa.cat).
- Algunas URLs legacy usan `http://www.manresa.cat/web/...`; el adapter normaliza a `web.manresa.cat`.
- e-TAULER podría aportar anuncios en el futuro vía API del consorcio; no implementado en esta PR.
