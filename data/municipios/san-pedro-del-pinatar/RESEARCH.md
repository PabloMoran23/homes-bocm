# San Pedro del Pinatar — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.sanpedrodelpinatar.es | WordPress (Colibri); concejalía Urbanismo |
| Urbanismo | https://www.sanpedrodelpinatar.es/concejalias/urbanismo/ | Estudios de detalle, modificaciones PP, formularios licencia (PDF) |
| PGOU | https://www.sanpedrodelpinatar.es/concejalias/urbanismo-2/plan-general-de-ordenacion-urbana/ | PGOU 1984 + avance PGOM |
| Planeamiento desarrollo | https://ayto.sanpedrodelpinatar.es/avance-pgmo/ | Planes parciales, estudios de detalle |
| Categoría urbanismo | https://www.sanpedrodelpinatar.es/category/urbanismo/ | Noticias y documentación |
| Sede electrónica (STA) | https://sede.sanpedrodelpinatar.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME | T-Systems STA |
| Tablón edictos | https://sede.sanpedrodelpinatar.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | `dataset_PTS2_TABLON` embebido en HTML (~45 entradas visibles) |
| Catálogo trámites | https://sede.sanpedrodelpinatar.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV`; urbanismo = keyword `PTS_PC_012` |
| IDERM / SITMURCIA | https://sitmurcia.carm.es/planeamiento-urbanistico | Visor regional planeamiento (PG 1984 digitalizado) |

## Listado de expedientes / proyectos

- **Web WP:** PDFs de estudios de detalle (Campoamor 3/16P, Artero Guirao 2024, Romería Virgen del Carmen), modificación PP sector U.P.2R-B (exp. 2025/8256V), PGOM en redacción.
- **Tablón STA:** JSON en página (`descriptionProc`, `externString`, `pubDateIni`, `remitent.description`). Histórico limitado en dataset embebido; pocos anuncios de Urbanismo en ventana actual.
- **Catálogo:** trámites clasificados bajo «Urbanismo y vivienda» (`PTS_PC_012`).

## Licencias

- No hay registro público de licencias concedidas con coordenadas.
- Formularios descargables en web (DRPO, LPO, DRO, comunicaciones previas, etc.) y trámites en catálogo sede.
- Tablón puede incluir edictos de licencia/obra (filtro textual).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITMURCIA: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs` capa `plu_ze_37_mun_uso_suelo`, filtro `Municipio='San Pedro del Pinatar'` (~100 polígonos, campo `Ambito` p. ej. `UP-8R.`, `UNP-3R1. Sector "VILLA ALEGRÍA"`).
  - Visor IDERM-STR (planeamiento general regional, actualización antigua para muchos municipios costeros).
  - No visor municipal ArcGIS/WFS propio enlazado a expedientes.
- **Estrategia:** tras scrape, extraer códigos UP-/UNP- o nombres de sector (Villa Alegría, Los Lorcas) y cruzar con índice WFS en memoria; rellenar `geom_geojson` cuando hay match.
- **Limitaciones:** WFS regional basado en PGOU 1984; PGOM en redacción no reflejado; sede con certificado SSL cadena incompleta (`insecure_ssl`); tablón sin geometría; licencias sin georreferencia.

## Notas técnicas

- Sede `sede.sanpedrodelpinatar.es`: certificado con emisor no reconocido en CA estándar → `insecure_ssl: true` en adapter.
- INE municipio: **30075**.
- Dominio legacy `ayto.sanpedrodelpinatar.es` aún sirve algunos PDFs.
