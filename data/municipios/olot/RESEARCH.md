# Olot — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.olot.cat |
| Planejament (índice) | https://www.olot.cat/ajuntament/planejament-i-gestio-urbanistica |
| Figures en tràmit | https://www.olot.cat/ajuntament/planejament-i-gestio-urbanistica/figures-en-tramit |
| Aprovades post-2003 | https://www.olot.cat/ajuntament/planejament-i-gestio-urbanistica/figures-aprovades-posterior-2003 |
| Aprovades pre-2003 | https://www.olot.cat/ajuntament/planejament-i-gestio-urbanistica/figures-aprovades-anterior-2003 |
| POUM (PDF estàtic) | http://poum.olot.cat |
| Catàleg tràmits (Urbanisme) | https://www.olot.cat/tramits/cataleg-de-tramits?filtre_221=S&cat_221=151 |
| Sede OAC | https://tramits.olot.cat/OAC/SegExpStandalone.jsp?idioma=ca |
| Assistent urbanisme | https://urbanisme.olot.cat |
| e-TAULER | https://tauler.seu.cat/v2/inici?idEns=1711430008 |
| Geoportal | https://sig.olot.cat/enmapa25/visor/geoportal |

## CMS y listado de expedientes / planeamiento

- Plataforma **iDisc d2web** (plantilles `/plantilles/olot/`, formularis `formu_*`, llistats `pln###`).
- Cada sección de planejament publica enlaces del tipo  
  `/ajuntament/planejament-i-gestio-urbanistica/<secció>/plnNNN/<slug>`.
- Ficha de proyecto: HTML estático con enlaces a documentos en `/files/doc<id>/<nombre>.pdf`.
- No hay API JSON pública; el scrape usa regex sobre HTML de listados y, opcionalmente, fichas (PDFs para fechas).

## Licencias de obra

- **No** hay listado público de licencias concedidas (tablón con coords).
- Catálogo de trámites filtrable por área «Urbanisme, Habitatge i Obres» (`cat_221=151`): fichas informativas de tipos de licencia/comunicación previa.
- **e-TAULER** (SPA React, `NOINDEX`) para anuncios/edictos; sin API estable documentada en esta run.
- El adapter ingiere trámites del catálogo + páginas informativas (patrón Mataró/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Geoportal municipal Enmapa25 (`https://sig.olot.cat/enmapa25/visor/geoportal`) y cartografía en `olot/planol-d-olot/geoportal`. Servicios REST/ArcGIS no respondieron de forma fiable desde el entorno cloud (timeout).
- **Estrategia:** No hay campo de expediente en capas consultables sin sesión/interacción en visor; los proyectos del portal son documentación PDF sin geometría enlazada.
- **Limitaciones:** Visor interactivo; planeamiento sin WFS/WMS público con join por código de expediente; e-TAULER no expone geometría.

## Limitaciones generales

- Muchas fichas históricas (~150+ post-2003); `max_detail_fetches` limita peticiones de enriquecimiento por ejecución.
- `robots.txt` impone `Crawl-delay: 60` (se respeta `request_delay_s` moderado).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
