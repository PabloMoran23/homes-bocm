# Durango — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.durango.eus |
| Bandos y anuncios (RSS) | https://www.durango.eus/es/rss/bandos-y-anuncios |
| Noticias (RSS) | https://www.durango.eus/es/rss/noticias |
| Sede electrónica (STA) | https://egoitza-sede.durango.eus/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Tablón de anuncios | https://egoitza-sede.durango.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Resoluciones urbanísticas | https://egoitza-sede.durango.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_URBANISTICAS |
| Boletines oficiales municipales | https://egoitza-sede.durango.eus/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_BOLOFICIAL |
| Participación (Parte Hartu) | https://partehartu.durango.eus/proyecto-de-participaci%C3%B3n |
| Transparencia | https://www.durango.eus/es/transparencia |

## Cómo se listan expedientes / proyectos

1. **Tablón STA** — Páginas `PTS2_TABLON` y `PTS2_URBANISTICAS` embeben JSON en `var dataset_PTS2_* = [...]` (patrón T-Systems STA, igual que Getafe/Leganés). Campos: `descriptionProc`, `pubDateIni`, `dboid`, `remitent`.
2. **Bandos y anuncios** — Listado en portada + **RSS** (`/es/rss/bandos-y-anuncios`). Ejemplo público: aprobación inicial de la 3.ª fase de urbanización UE-7 Azoka-Montevideo.
3. **Parte Hartu** — Procesos abiertos con fechas (p. ej. consulta previa modificación NNSS en PERI-1 Ferrocarril, oct–nov 2026).
4. **Boletín oficial municipal** — STA `PTS_BOLOFICIAL` (PDF/HTML); no API JSON dedicada.

En el entorno del agente cloud, `www.durango.eus` y la sede responden **403** o **timeout** desde IPs externas; el adapter sigue intentando fetch (funciona desde redes locales/CI en Euskadi).

## Licencias de obra

- Trámites en sede STA; **no** hay dataset público de licencias concedidas con dirección.
- El adapter registra filas **informativas** de trámites + licencias detectadas en tablón (si las hubiera).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Foral de Bizkaia — ArcGIS `PX_Durango_inf` (`LurraldeAntolamendua_PlanificacionTerritorial`), capas de clasificación/calificación PGOU (p. ej. 50, 71, 91, 97).
  - Query: `.../MapServer/{layer}/query?returnGeometry=true&outSR=4326&f=geojson`, filtro `DESCRIPCION` / `ETIQUETA` por tokens del título (Azoka, Ferrocarril, PERI…).
  - Servicio hermano `PX_Durango_ord` (ordenación) — principalmente propuesta PGOU, sin enlace a expediente.
- **Estrategia:** enriquecer proyectos con polígonos PGOU cuando el título contiene topónimos coincidentes; si no hay match, geocode usa centroide municipal + jitter.
- **Limitaciones:** sin visor municipal de expediente enlazado; tablón/PDF sin georef directa; portal principal puede bloquear bots.

## Limitaciones generales

- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
- CMS municipal + STA; cookies en portal.
- Sede puede requerir tiempos de respuesta largos (>25 s) en horas punta.
