# Santa Perpètua de Mogoda — investigación portal ayuntamiento

## Fuentes principales

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.staperpetua.cat | Urbanisme: llistats HTML `article-item` amb títol, data i enllaç |
| Sede STA | https://seu.staperpetua.cat/sta/CarpetaPublic/Public?APP_CODE=STA&PAGE_CODE=PTS2_HOME | Catàleg tràmits, tabló, consulta expedients (identificació) |
| PIU / geoportal | https://piu.staperpetua.cat/geoportal/ | Consulta urbanística parcel·la a parcel·la (Nexus Geographics + OpenLayers WMS) |
| RPUC Gencat | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08260 | Expedients de planejament registrats |
| MUC Gencat | https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08260 | Mapa urbanístic de Catalunya |

## Semillas de proyectos

- `/ajuntament/normativa/urbanisme/planejament-en-tramit`
- `/ajuntament/normativa/urbanisme/projectes-en-exposicio-publica`
- `/ajuntament/projectes-urbanistics`
- `/ajuntament/normativa/urbanisme/planejament-derivat`
- `/ajuntament/normativa/urbanisme/modificacions-puntuals-o-altres-figures-relatives-al-planejament-general`
- `/ajuntament/normativa/urbanisme/exposicio-publica-activitats` (activitats / IP)

Formato de listado: `<li class="article-item">` → `<p class="subtitle">`, `<div class="date">DD/MM/YYYY</div>`, enllaç a fitxa o PDF.

Códigos de expediente en título (p. ej. `2022/5737c`, `2023/7220A`).

## Licencias

- Página municipal `/ajuntament/normativa/urbanisme/llicencies-i-comunicacions-dobres`: actualmente sin filas publicadas (“No s'han trobat resultats”).
- Trámites informativos: FUE informe urbanístic, guías PDF comunicación previa, enlaces `PTS_CATSERV2` / `CATALOGO` en `/temes/urbanisme-i-habitatge`.
- Tablón STA (`PTS2_TABLON` / `PTS_TABLON`): no accesible de forma fiable desde el entorno cloud (timeout >90s); el adapter documenta URLs desde la web.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - PIU (`piu.staperpetua.cat`): visor WMS/OpenLayers por parcela; sin API REST pública enlazada al código de expediente del listado municipal.
  - MUC / RPUC (Gencat, INE **08260**): cartografía y expedientes de planejament; no hay join automático expediente web ↔ polígono en scrape determinista.
- **Estrategia adapter:** metadatos + URLs de referencia; el orquestador aplica centroide municipal (`manifest.config.centroid`) + geocode. Enriquecimiento futuro: WMS PIU por ref. cadastral si aparece en fichas.
- **Limitaciones:** sede STA con latencia alta desde cloud; PIU Angular sin endpoint GeoJSON documentado; licencias sin listado tabular público.

## Limitaciones generales

- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Sede `seu.staperpetua.cat` responde lento o no responde en algunos entornos automatizados.
- Licencias concedidas no se publican en listado dedicado; solo trámites/edictes puntuales.
