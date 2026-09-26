# Santa Cruz de La Palma — investigación portal ayuntamiento

Municipio: **Santa Cruz de La Palma** (`santa-cruz-de-la-palma`) — Canarias, provincia Santa Cruz de La Palma. Boletín: `boc_canarias` (2 avisos BOCM). INE: 38037.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (CMS Bootstrap/Laravel) | https://www.santacruzdelapalma.es/web/sclapalma |
| Área Planeamiento (urbanismo) | https://www.santacruzdelapalma.es/web/sclapalma/areas/informacion/10 |
| Anuncios y convocatorias | https://www.santacruzdelapalma.es/web/sclapalma/documentos/anuncios-convocatorias |
| Documentos útiles (formularios licencias) | https://www.santacruzdelapalma.es/web/sclapalma/documentos/documentos-utiles |
| Noticias municipales | https://www.santacruzdelapalma.es/web/sclapalma/noticia/noticias-sclapalma |
| Sede electrónica (Maggioli ATM Angular) | https://sede.santacruzdelapalma.es |
| Transparencia sede | https://sede.santacruzdelapalma.es/transparencia |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-santa-cruz-de-la-palma |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38037/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** portal corporativo propio (Bootstrap 5, rutas `/web/sclapalma/areas/informacion/{id}`). El área **10** corresponde a «Planeamiento».
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-santa-cruz-de-la-palma` con **90 recursos** (25 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 3 documentos con visor OpenLayers y botón «Localizar» (`findRecintoByDocumento`); geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Noticias:** listado paginado en `/noticia/noticias-sclapalma` con URLs cifradas (`/noticias/eyJpdiI6...`); el adapter filtra por keywords urbanísticas en las primeras 5 páginas.
- **Sede `sede.santacruzdelapalma.es`:** SPA Angular Maggioli ATM; sin API pública de tablón/edictos scrapeable (rutas devuelven HTML de la SPA).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Formularios descargables en «Documentos útiles»: solicitud licencia obra mayor (id 60), obra menor (61), cédula urbanística (62).
- Trámites vía sede electrónica Maggioli.
- El adapter incluye páginas informativas de la sede y enlaces a formularios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38037); para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (3 polígonos); noticias y licencias sin geometría enlazable; sede SPA sin tablón HTML.

## Limitaciones generales

- Sede electrónica es SPA sin tablón scrapeable (documentado; no bloquea ingesta).
- Sin tablón de licencias concedidas en abierto.
- Portal CMS mezcla noticias generales con urbanismo — filtro por keywords.
- Área Planeamiento (id 10) no publica listado de expedientes individuales, solo enlaces a documentos y noticias.
