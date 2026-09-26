# Guía de Isora — investigación portal ayuntamiento

Municipio: **Guía de Isora** (`guia-de-isora`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso BOCM). INE: **38019**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress FoundationPress) | https://www.guiadeisora.org/corp/ |
| Área urbanismo | https://www.guiadeisora.org/corp/areas-municipales/urbanismo/ |
| PGOU / planeamiento | https://www.guiadeisora.org/corp/areas-municipales/urbanismo/plan-general-de-ordenacion-urbana/ |
| Otras formas de ordenación | https://www.guiadeisora.org/corp/areas-municipales/urbanismo/otras-formas-de-ordenacion/ |
| Trámites urbanísticos (modelos PDF) | https://www.guiadeisora.org/corp/areas-municipales/urbanismo/tramites/ |
| Sede electrónica (espublico gestiona) | http://guiadeisora.sedelectronica.es/ |
| Tablón de anuncios | http://guiadeisora.sedelectronica.es/board |
| Transparencia | https://transparencia.guiadeisora.es |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-guia-de-isora |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38019/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Guia/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + FoundationPress bajo `/corp/`; PDFs en `/corp/download/modelos/urbanismo/`.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-guia-de-isora` con **53 recursos** (~15 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP/FIP).
- **GEOBDP:** 15 documentos con visor OpenLayers; geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Web municipal:** páginas de PGOU con PDFs de modificaciones puntuales (Abama, Cueva del Polvo, Villa Erques, etc.), estudios de detalle y proyectos de compensación.
- **Sede espublico:** tablón `/board` con filas HTML (`class_name`, `class_folderCode`, `preview-document`); actualmente mayoritariamente subvenciones/convocatorias, sin filas urbanísticas en el momento de la investigación.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Modelos de solicitud en WP (`/tramites/` — licencias, declaración responsable, informes).
- Trámites vía sede espublico (`/dossier`); el adapter incluye páginas informativas del tablón y modelos WP.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38019); para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (15 polígonos); licencias y tablón sede sin geometría enlazable; PDFs WP sin georreferencia.

## Limitaciones generales

- Sin listado histórico público de licencias concedidas.
- Tablón sede accesible pero sin anuncios urbanísticos en la fecha de investigación.
- WP mezcla cultura/deportes con urbanismo — filtro por keywords en adapter.
