# El Pinar — investigación portal ayuntamiento

Municipio: **El Pinar** (`el-pinar`) — Canarias, provincia El Pinar/El Hierro. Boletín: `boc_canarias` (1 aviso BOCM). INE: 38901.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo (Joomla) | https://www.aytoelpinar.org |
| Portal turismo (Joomla K2, enlace al ayto) | https://www.elpinardeelhierro.es |
| Sede electrónica (espublico gestiona) | https://elpinardeelhierro.sedelectronica.es |
| Tablón de anuncios sede | https://elpinardeelhierro.sedelectronica.es/board |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-el-pinar |
| GEOBDP PGO El Pinar (doc 1403) | https://geobdp.grafcan.es/core/documentos/1403.html |
| IDECanarias PGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/EH/Pina/PGO/indice.html |
| Archivo planeamiento Canarias (El Hierro) | https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=3&provincia=38 |

## Cómo se listan expedientes / planeamiento

- **CMS corporativo:** Joomla en `aytoelpinar.org` con documentación normativa del PGO (fichas de suelo, anejos PDF). **Inaccesible desde CI** (502 Bad Gateway, sep-2026); el adapter no depende de él.
- **Sede espublico:** tablón de anuncios público (`/board`) con filas HTML `data-label` (Descripción, Expediente, Procedimiento, Categoría, Fecha). Mayoría de anuncios administrativos/fiscales; sin licencias de obra publicadas.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-el-pinar` con **3 instrumentos** (9 recursos):
  1. PERU La Restinga (GEOBDP doc 644)
  2. Revisión Parcial PGO Frontera (GEOBDP doc 645)
  3. PGO El Pinar aprobación definitiva 2022 (GEOBDP doc 1403, BOC 118/2022)
- **Archivo planeamiento Canarias:** formulario JSP por isla/municipio (El Hierro = provincia 38, municipio 3); 8 instrumentos generales + 3 de desarrollo; sin API REST.
- **IDECanarias:** índices HTML con documentación PDF del PGO.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica (licencias urbanísticas, comunicaciones previas) — consulta de expedientes requiere identificación Cl@ve.
- El adapter incluye páginas informativas (tablón sede + archivo planeamiento Canarias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `App.Map.zoomToExtent`
  - IDECanarias WMS regional (`idecan2.grafcan.es/ServicioWMS/Planeamiento`) sin query por expediente
  - Visor embed Grafcan municipal genérico (`visor.grafcan.es`) sin enlace a expedientes del ayto
- **Estrategia:** emparejar recursos SITCAN con doc GEOBDP por URL; descargar `zoomToExtent` y reproyectar EPSG:32628 → WGS84.
- **Resultado:** doc **1403** (PGO El Pinar) tiene `MultiPolygon` válido; docs **644** y **645** devuelven `features: []` (sin polígono enlazable).
- **Limitaciones:** portal corporativo caído en CI; sede sin licencias georreferenciadas; solo 1/3 instrumentos con geometría vectorial.

## Limitaciones generales

- `aytoelpinar.org` responde 502 desde el entorno del agente (documentado; no bloquea ingesta vía SITCAN).
- Sin re-parse BOCM; 1 entrada en `boc_canarias` ya en `projects.json`.
- Municipio joven (2007, segregado de Frontera); planeamiento histórico de Frontera aparece en SITCAN por continuidad territorial.
