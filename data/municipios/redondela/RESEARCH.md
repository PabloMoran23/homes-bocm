# Redondela — investigación portal ayuntamiento

Municipio: **Redondela** (`redondela`) — Galicia, provincia Pontevedra.  
INE SIOTUGA: **36045**. Sin boletín regional asociado en cola (`bocm_count: 0`).

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa (WordPress) | https://redondela.gal |
| PXOM (gl / es) | https://redondela.gal/gl/pxom/ · https://redondela.gal/es/pxom/ |
| Sede electrónica | https://redondela.sedelectronica.gal/ |
| Sede (enlace web) | https://redondela.gal/sede-electronica/ |
| Portal documentación PXOM | https://redondela-pxom.gal/ (403 desde cloud; PDFs indexados en buscadores) |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36045&lang=es_ES |
| SIOTUGA WMS | https://siotuga.xunta.gal/siotuga/ws?codine=36045 |
| ArcGIS Hub | https://redondela.maps.arcgis.com/ |
| App «O PXOM nun clic» | https://redondela.maps.arcgis.com/apps/instant/sidebar/index.html?appid=f29c9e98a39342aab3369148a80b1f63 |
| Experience PXOM 3.0 | https://experience.arcgis.com/experience/81494d91a3ae4e8ba912219a05a10ca9 |

## Proyectos / expedientes

- **CMS:** WordPress en `redondela.gal` (Elementor). La sección `/gl/pxom/` documenta el proceso del nuevo PXOM (2021–2025) y enlaces al visor.
- **Inventario normativo:** **SIOTUGA** — ~13 instrumentos de plan xeral / normas (`idclase` 14) y ~27 de desenvolvemento (`idclase` 13) para INE **36045**. POST `assets/inventario/query_document.php` con `id`, `token` (cookie de sesión) e `idclase`.
- **Cartografía:** FeatureServer ArcGIS `T36045_PXOM_AI_*` (organización municipal en `services-eu1.arcgis.com/KmoBn3Qii9gbOa4C`). Capas de malla urbanística (SUC 2000 m, clasificación 5000 m, delimitación).
- **Web municipal:** respuesta **403 Forbidden** a scrapers desde entorno cloud; el adapter usa **wayback_fallback** (`web.archive.org/web/2024/`) para enlaces/PDFs en semillas PXOM cuando el origen directo falla.

## Licencias de obra

- No hay tablón público scrapeable de **licencias concedidas** con dirección y fecha.
- Tramitación vía **sede electrónica** (`redondela.sedelectronica.gal`, plataforma OpenGovernment con URLs `info.0?x=…`); acceso desde cloud devuelve redirección sin HTML estable.
- El adapter ingiere filas **informativas** (sede + visor PXOM / trámites).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS FeatureServer municipal: `T36045_PXOM_AI_Malla_SUC_2000_(VP)` (campo `Nombre`), `T36045_PXOM_AI_Malla_5000_(VP)` (campo `NOMBRE`).
  - WMS SIOTUGA por concello (`codine=36045`).
  - Visor «O PXOM nun clic» (ArcGIS Instant Apps / Experience Builder).
- **Estrategia:** Metadatos desde SIOTUGA + semillas web/ArcGIS; el adapter intenta `_fetch_geometry` buscando tokens del título en capas ArcGIS (`LIKE` sobre `Nombre`/`NOMBRE`). Sin join estable código expediente SIOTUGA ↔ polígono.
- **Limitaciones:** Muchos instrumentos solo tienen metadatos normativos sin polígono enlazable por nombre; web corporativa bloqueada (403); sede con sesión opaca; `redondela-pxom.gal` bloqueado desde cloud.

## Limitaciones generales

- BOCM: sin boletín asociado.
- Nombres de documentos en gallego; fechas en `fechaaddef` (SIOTUGA).
- Sync Supabase: depende de `SUPABASE_DB_URL` en CI/agente.

## Adapter

- `municipio/adapters/redondela.py` — SIOTUGA (36045) + semillas ArcGIS/PXOM + crawl wayback de `/pxom/` + enriquecimiento geometría ArcGIS parcial.
