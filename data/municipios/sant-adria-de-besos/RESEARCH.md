# Sant Adrià de Besòs — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Plone) | https://www.sant-adria.cat/ (redirige desde http://www.sant-adria.net) |
| Urbanisme | https://www.sant-adria.cat/sant-adria-per-temes/territori/urbanisme |
| IP planejament | https://www.sant-adria.cat/sant-adria-per-temes/territori/urbanisme/tramit-dinformacio-publica-planejament-urbanistic |
| Publicitat planejament | https://www.sant-adria.cat/sant-adria-per-temes/territori/urbanisme/publicitat-del-planejament-urbanistic |
| Convenis urbanístics | https://www.sant-adria.cat/sant-adria-per-temes/territori/urbanisme/publicitat-dels-convenis-urbanistics |
| Sede STA | https://seu.sant-adria.net/ |
| Tablón edictos | https://seu.sant-adria.net/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON |
| Catálogo trámites | `PAGE_CODE=PTS_CATSERV` / `CATALOGO` (dataset `CATSERV`) |
| Seu-e tràmits urbanisme | https://seu-e.cat/ca/web/santadriadebesos/tramits-i-gestions/-/tramits/classificacio/urbanisme |
| RPUC (enlace desde IP) | https://dtes.gencat.cat/rpucportal/ |
| Geoportal AMB cartografía | https://geoportalcartografia.amb.cat/AppGeoportalCartografia2/index.html |

## Proyectos / expedientes

- **Listado principal:** página Plone *Tràmits d'informació pública planejament urbanístic* con enlaces a PDFs (`/fitxers/documents/…`) y documentos bajo `/sant-adria-per-temes/territori/documents/…`.
- **Publicitat:** mezcla de enlaces al BOP Diputació Barcelona y documentos locales (estudis de detall, PEUs, etc.).
- **Convenis:** sección dedicada + carpeta Territori/Convenis.
- **Formato:** HTML Plone; sin API JSON pública. Fechas inferidas del título/URL cuando no hay metadato explícito.
- **GIS:** capa **AMB Planejament/Expedients** MapServer/3 filtrada por `CODI_INE='08169'` (~119 expedientes con polígono WGS84).

## Licencias

- No hay listado público de licencias concedidas (tablón PTS2_TABLON sin filas).
- Trámites relacionados en catálogo STA (`Urbanisme: Informes/Certificats urbanístics`) y seu-e (p. ej. informe urbanístic per activitats).
- El adapter registra trámites informativos de licencias/obras, no concesiones nominales.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS REST: `https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament/Expedients/MapServer/3`
  - Campos: `NOMEXP`, `DGU`, `URL`, `DAPRDEF`; geometría polígono (`returnGeometry=true`, `outSR=4326`, `f=geojson`).
  - Visor cartográfico AMB (contexto metropolitano); MUC Gencat (`municipi=08169`) no respondió en el entorno del agente.
- **Estrategia:** ingestar expedientes AMB como proyectos con `geom_geojson`; enlazar documentos Plone y enriquecer por coincidencia de título/`NOMEXP`.
- **Limitaciones:** documentos IP en PDF sin georreferencia directa; tablón vacío; licencias sin coords; join texto↔GIS aproximado.

## Limitaciones generales

- Dominio legacy `www.sant-adria.net` HTTPS devuelve cuerpo vacío; usar `www.sant-adria.cat`.
- Crawl acotado a rutas `territori` / `fitxers` (máx. ~40 páginas).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
