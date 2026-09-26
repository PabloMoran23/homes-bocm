# Aspe — investigación portal ayuntamiento

**Municipio:** Aspe (Alicante, Comunitat Valenciana)  
**INE:** 03009  
**Boletín:** DOGV (`dogv`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://aspe.es | WordPress (tema The7) |
| Tablón electrónico | https://aspe.es/tablon-de-anuncios-electronico/ | Índice CPT `anuncio-electronico` |
| Tablón histórico | https://aspe.es/tablon-de-anuncios/ | CPT `anuncio-tablon` (archivo 2015–2017) |
| Normativa urbanística | https://aspe.es/normativa-urbanistica/ | PGOU refundido + planos PDF |
| Sede electrónica | https://sede.aspe.es/ | STA (Software Tramitación Ayuntamientos) |
| Catálogo trámites | https://sede.aspe.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV` JSON embebido |
| Tablón sede (no usable) | https://sede.aspe.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | Widget AJAX sin JSON embebido |

### Sitemaps WordPress (listado determinista)

- `https://aspe.es/wp-sitemap-posts-anuncio-electronico-1.xml` (~2000 URLs)
- `https://aspe.es/wp-sitemap-posts-anuncio-electronico-2.xml` (~698 URLs)
- `https://aspe.es/wp-sitemap-posts-anuncio-tablon-1.xml` (~89 URLs)

## Cómo se listan expedientes / proyectos

1. **WordPress CPT `anuncio-electronico`:** edictos y anuncios publicados en el tablón electrónico. Título inferido del slug URL; fecha desde `<lastmod>` del sitemap. Incluye información pública, licencias ambientales, modificaciones PGOU, reparcelaciones, etc.
2. **WordPress CPT `anuncio-tablon`:** archivo histórico (2015–2017) con el mismo patrón.
3. **Normativa urbanística:** PDFs del PGOU (refundido, clasificación del suelo, sectores) enlazados en HTML estático.
4. **ICV WFS:** capas de zonificación del planeamiento autonómico (sectores/planes parciales homologados).

## Cómo se publican licencias

- **No hay listado público de concesiones** de licencias de obra con dirección/fecha individual.
- **Catálogo STA:** trámites `URB-1` … `URB-25` (licencias, DR, comunicaciones previas) accesibles vía sede electrónica; son páginas informativas/tramitación, no concesiones.
- **Tablón WP:** algunos edictos de licencia ambiental o notificaciones urbanísticas (`edicto-licencia-*`, `licencia ambiental`).
- **Tablón STA:** página PTS2_TABLON existe pero carga datos vía widget JavaScript (`callWidgetEventExecuteOn`); no expone `dataset_PTS2_TABLON` en HTML inicial.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `Planeamiento.Zonificacion`
  - Filtro: `cod_ine_mun='03009'`
  - Formato: `application/json; subtype=geojson`, `srsName=EPSG:4326`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** paginar WFS por `startIndex` (offsets 0–13500); agrupar polígonos por `(denominaci, expediente)`; emparejar título de anuncio con zona ICV por sector/nombre (`_match_icv_zone`).
- **Limitaciones:**
  - No hay visor municipal propio ni enlace expediente→geometría.
  - ICV aporta zonas de planeamiento (sectores/PGOU), no parcelas de licencias individuales.
  - Tablón STA no scrapeable sin ejecutar JS del widget.
  - Muchos anuncios son PDFs sin georreferencia explícita.

## Limitaciones generales

- Tablón sede STA (PTS2_TABLON) requiere widget AJAX — no incluido en adapter.
- Licencias de obra: solo trámites informativos + edictos puntuales en tablón WP.
- Sitemap incluye muchos anuncios no urbanísticos (padrón, empleo); filtrados con regex `RE_NOISE`.
- PGOU PDFs en normativa son documentos estáticos sin metadatos de fecha fiable.

## Referencias de patrón

- ICV WFS + matching zonas: `municipio/adapters/alfafar.py`, `municipio/adapters/denia.py`
- STA catálogo CATSERV: `municipio/adapters/parla.py`, `municipio/adapters/denia.py`
