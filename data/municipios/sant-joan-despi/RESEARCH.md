# Sant Joan Despí — portal ayuntamiento

| Campo | Valor |
|-------|--------|
| Slug | `sant-joan-despi` |
| INE | 08273 |
| Web | https://sjdespi.cat |
| Sede | https://seu-e.cat/es/web/santjoandespi |

## Fuentes

### Información pública de proyectos (Drupal)

- ES: https://sjdespi.cat/es/la-ciudad-por-temas/urbanismo-y-publica/informacion-publica-de-proyectos (node/306)
- CA: https://sjdespi.cat/la-ciutat-per-temes/urbanisme-i-publica/informacio-publica-projectes
- Listado largo de PDFs en `div.file-link` con título legible + enlace a `/sites/default/files/YYYY-MM/*.pdf`.
- Fecha aproximada: carpeta `YYYY-MM` en la URL del PDF.

### Expedientes en trámite (seu-e / transparencia)

- Página municipal (iframe): https://sjdespi.cat/es/la-ciudad-por-temas/urbanismo-y-publica/expedientes-en-tramite
- Contenido real: https://seu-e.cat/es/web/santjoandespi/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic
- Liferay AOC: enlaces `/documents/27745/{repo}/{NOMBRE_EXPEDIENTE}/{uuid}` (PGM, GPU, PMU, URB, PPE, etc.) y PDFs DOGC/BOP.

### Planeamiento vigente

- Texto remite al Registro de planeamiento urbanístico de Catalunya (RPUC): https://dtes.gencat.cat/rpucportal/
- PDUM/POUM vía AMB: https://www.amb.cat/es/web/territori/gestio-i-organitzacio/numamb (municipio 08169 en ámbito metropolitano).

### Licencias de obra

- No hay tablón público de concesiones identificado.
- Trámites informativos: https://sjdespi.cat/es/ayuntamiento/licencias-obras/licencia-urbanistica
- Sede: https://seu-e.cat/es/web/santjoandespi/seu-electronica y catálogo de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal municipal (enmapa): https://sjdespi.enmapa.com/geoportal/ (embed en https://sjdespi.cat/es/la-ciudad-por-temas/urbanismo-y-publica/geoportal-urbanistico)
  - Visor guía: https://sjdespi.enmapa.com/visor/guia
  - MUC Generalitat (consulta por municipio 08273): https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08273
  - Mapa urbanístico Catalunya (ICGC): enlace desde https://sjdespi.cat/es/ayuntamiento/informacion-urbanistica
- **Estrategia:** los listados scrapeados (PDFs / seu-e) no exponen `objectId` ni código de parcela enlazable de forma estable; enmapa responde 403 (Cloudflare) a peticiones automatizadas sin navegador.
- **Limitaciones:** sin join determinista expediente→polígono; el orquestador usará centroide municipal + jitter. Revisión manual posible vía visor enmapa/MUC.

## Adapter

- `municipio/adapters/sant_joan_despi.py` — `SantJoanDespiAyuntamientoAdapter`
