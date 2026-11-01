# Rubí — investigación portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Web municipal (Plone) | https://www.rubi.cat |
| Urbanisme | https://www.rubi.cat/ca/temes/urbanisme |
| Planejament vigent | https://www.rubi.cat/ca/temes/urbanisme/planejament-vigent-i-gestio-urbanistica/planejament-i-gestio-urbanistica |
| POUM (revisión en curso) | https://www.rubi.cat/ca/temes/urbanisme/poum |
| Documentación POUM (PDF) | https://www.rubi.cat/fitxers/documents-ok/area-de-serveis-territorials/poum/ |
| Licencias (info) | https://www.rubi.cat/ca/temes/urbanisme/llicencies-i-disciplina-1/llicencies-i-disciplina-dobres |
| Seu electrònica | https://seu.rubi.cat |
| Catálogo trámites | https://seu.rubi.cat/catalogoTramites/listTemes |
| Sitemap | https://www.rubi.cat/sitemap.xml.gz |

## Proyectos / planeamiento

- **CMS:** Plone 5 (`x-cache-operation: plone.app.caching`). Carpetas de urbanisme y microsite POUM con fases (avance, aprobación inicial/provisional, exposición pública, consell consultiu).
- **Listado:** No hay visor de expedientes ni RSS con ítems en `planejament-i-gestio-urbanistica` (canal vacío). Contenido útil vía **sitemap** + noticias/notas de prensa sobre POUM, PMU (sector Cremalleras), PEU extractivas, etc.
- **PDFs:** Repositorio `fitxers/documents-ok/area-de-serveis-territorials/poum/` (actas consell consultiu, informes).
- **Referencias estatales:** RPUC (`municipiSel=08184`) y MUC visor Generalitat (`municipi=08184`) — consulta informativa, sin scrape de expediente por código en el adapter.

## Licencias

- **No** hay dataset ni tablón público de licencias concedidas (comparar con sedes STA `opensiac` de otros municipios catalanes).
- Página web enlaza a **tràmits relacionats amb obres** en `seu.rubi.cat/catalogoTramites/listTemes` (p. ej. certificado compatibilidad urbanística, trámites de obra).
- El adapter ingiere filas **informativas** de trámites (patrón Pozuelo / Mataró).

## Limitaciones

- `www.rubi.cat` puede devolver **403** a clientes sin User-Agent de navegador; usar UA identificable (`poc-bocm-rubi/1.0`).
- Descarga del sitemap ~50s; timeout recomendado ≥120s en cloud.
- Muchas URLs de noticias son participación/comunicación POUM (metadatos útiles, sin geometría).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - MUC visor Generalitat: https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08184&set-locale=ca — planeamiento por capas municipales, sin API REST por expediente del ayuntamiento.
  - RPUC: https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08184 — búsqueda manual, sin enlace estable expediente→polígono en portal Rubí.
  - ICV / WFS por código INE: sin servicio accesible automatizable desde el agente (error página Generalitat).
  - Web Rubí: sin visor ArcGIS/GeoServer enlazado a expedientes urbanísticos individuales.
- **Estrategia:** Orquestador aplicará `centroid` del manifest + jitter (`[41.4923, 2.0324]`).
- **Limitaciones:** Solo documentación PDF y noticias; no hay `geom_geojson` en fuentes públicas enlazables al listado scrapeado.
