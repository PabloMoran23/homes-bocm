# Santa Cruz de Tenerife — investigación portal ayuntamiento

Municipio: **Santa Cruz de Tenerife** (`santa-cruz-de-tenerife`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (2 avisos BOCM). INE: 38038.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (Typo3 + t3sbootstrap) | https://www.santacruzdetenerife.es |
| Urbanismo (área municipal) | https://www.santacruzdetenerife.es/web/servicios-municipales/urbanismo |
| Noticias urbanismo | https://www.santacruzdetenerife.es/web/servicios-municipales/urbanismo/noticias |
| Gerencia Municipal de Urbanismo (Drupal 10) | https://www.urbanismosantacruz.es |
| Anuncios GMU | https://www.urbanismosantacruz.es/es/anuncios |
| Planeamiento vigente / en trámite | https://www.urbanismosantacruz.es/es/planeamiento-vigente |
| Procedimientos (licencias) | https://www.urbanismosantacruz.es/es/procedimientos |
| Sede municipal | https://sede.santacruzdetenerife.es/sede/inicio |
| Sede GMU | https://sede.urbanismosantacruz.es |
| Tablón STA (OVC) | https://ovc.santacruzdetenerife.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-santa-cruz-de-tenerife |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38038/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/SCTf/ |

## Cómo se listan expedientes / planeamiento

- **CMS ayuntamiento:** Typo3 con extensión `sc_localizaciones` (Leaflet) en el portal corporativo; noticias de urbanismo en `/web/servicios-municipales/urbanismo/noticias`.
- **GMU (Gerencia Municipal de Urbanismo):** Drupal 10 en `urbanismosantacruz.es` con secciones de anuncios, planeamiento vigente/en trámite, procedimientos y documentación técnica (PDFs en `/sites/default/files/Planeamiento/`).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-santa-cruz-de-tenerife` con **62 recursos** (20 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 14 documentos con visor OpenLayers; geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Tablón STA:** formulario ASP en `ovc.santacruzdetenerife.es` (sin RSS ni listado HTML scrapeable en CI).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Procedimientos informativos en GMU: M108 licencia urbanística, M114 comunicación previa de obras, M311/M312 actividad clasificada, segregación-parcelación, etc.
- Trámites vía sede GMU (`sede.urbanismosantacruz.es`) y sede municipal; el adapter incluye páginas informativas de procedimientos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente individual
  - GMU cartografía histórica (mapas estáticos, sin WFS público por expediente)
- **Estrategia:** indexar documentos GEOBDP del municipio; para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~14 polígonos); anuncios GMU y licencias sin geometría enlazable; tablón STA no scrapeable.

## Limitaciones generales

- Capital insular con portal dual (Typo3 + Drupal GMU); anuncios recientes limitados en listado público (3-4 activos + pasados).
- Sin tablón de licencias concedidas en abierto con coordenadas.
- Typo3 noticias mezclan obras de emergencia con planeamiento — filtro por keywords.
