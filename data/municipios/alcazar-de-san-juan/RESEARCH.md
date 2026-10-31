# Alcázar de San Juan — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|--------|-----|
| Web corporativa | https://alcazardesanjuan.es |
| Ordenación territorial y urbanística | https://alcazardesanjuan.es/ordenacion-territorial-y-urbanistica/ |
| Sede electrónica (STA/TAO) | https://sede.alcazardesanjuan.es |
| Tablón de anuncios | https://sede.alcazardesanjuan.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON |
| Catálogo de trámites | https://sede.alcazardesanjuan.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |

## Proyectos / planeamiento

- **WordPress:** la página de urbanismo enlaza PDFs del PGOU, modificaciones puntuales, estudios de detalle y ordenanzas (`wp-content/uploads/…`). No hay API REST pública de expedientes; el adapter extrae enlaces PDF de la semilla.
- **Tablón sede (STA):** el HTML incluye `var dataset_PTS_TABLON = […]` (~150 anuncios). Campos útiles: `descriptionProc`, `externString` (referencia), `pubDateIni`, `remitent.description` (p. ej. «Urbanismo»). Detalle: `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_TABLON`.
- **Catálogo CATSERV:** `var dataset_CATSERV` con trámites urbanísticos marcados con keyword `PTS_PC_012` (urbanismo). Detalle: `DETALLE={dboid}&PAGE_CODE=CATALOGO`.

## Licencias

- Las **concesiones** aparecen en el tablón como «exposición pública» / «licencia urbanística» (remitente Urbanismo).
- No hay listado tabular dedicado solo a licencias concedidas.
- El catálogo incluye trámites informativos (obra mayor/menor, declaración responsable, primera ocupación, etc.) — el adapter los ingiere como filas de trámite (patrón Pozuelo/Móstoles).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM — `Vector/Planeamiento_Municipal/MapServer/0`, filtro `COD_INE='13005'`, `f=geojson`, `outSR=4326`. Devuelve el contorno del PGOU municipal (1 feature) y enlace ZIP en `DESCARGA`.
  - Visor SIU Castilla-La Mancha (regional): https://castillalamancha.maps.arcgis.com/ — sin campo expediente del ayuntamiento.
- **Estrategia:** fila PGOU desde CLM + adjuntar polígono PGOU a registros cuyo título menciona PGOU/plan general; resto sin `geom_geojson`.
- **Limitaciones:** PDFs y anuncios del tablón no traen parcela georreferenciada; no hay WFS municipal ni visor local enlazado a `externString`/expediente.

## Limitaciones técnicas

- Tablón TAO: dataset JSON embebido (no API AJAX separada); respuesta lenta (~25 s).
- Mezcla de anuncios de Personal/RRHH con urbanismo; filtrado por remitente y regex.
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
