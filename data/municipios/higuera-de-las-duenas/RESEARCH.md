# Higuera de las Dueñas — investigación portal ayuntamiento

**Municipio:** Higuera de las Dueñas (Castilla y León, Ávila)  
**Fecha:** 2026-08-08

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.higueradelasduenas.es | CMS estático DipuÁvila 2020 |
| Normas urbanísticas | https://www.higueradelasduenas.es/ayuntamiento/normas-urbanisticas/ | 9 fichas (modificaciones, estudios de detalle S-4/S-10, enlace PLAU) |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=095 | Archivo planeamiento vigente (cód. municipio 095) |
| PDFs planeamiento | https://www.higueradelasduenas.es/docus/pdfs/normas/ | Planos y documentación por sector (sunc-4, sunc-10, mod01–mod06) |
| Sede electrónica (espublico gestiona) | https://higueradelasduenas.sedelectronica.es/board | Tablón de anuncios (vacío a 2026-08-08) |
| Sede trámites | https://higueradelasduenas.sedelectronica.es/dossier | Catálogo de trámites (lento; sin filas urbanismo visibles en prueba) |
| Sede inicio | https://higueradelasduenas.sedelectronica.es/info | Redirige a /info.0 |

## Cómo se listan expedientes

- **Web DipuÁvila:** listado HTML en `/ayuntamiento/normas-urbanisticas/` con bloques `<div class="fch" data-ids="...">` → artículo con `<h1>`, `<time datetime>`, enlace a `.html` de detalle. Los PDFs están en rutas predecibles bajo `/docus/pdfs/normas/`.
- **PLAU CyL:** consulta pública por código provincia/municipio (05/095); no hay API JSON local.
- **Tablón sede:** HTML espublico estándar (`preview-document`); actualmente sin filas en `<tbody>`.
- **Sin visor de expedientes** ni listado JSON de IP en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Información pública de licencias aparece en BOCYL (p. ej. expte. 57/2024 sector 6) y se remite a la sede, pero el tablón no expone archivo scrapeable.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Higuera de las Dueñas'`
  - Resultado: 1 instrumento (NNSS) + 13 sectores con `MultiPolygon`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer fichas web por coincidencia de sector (S-4, S-10, etc.) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia en portal.
  - Tablón sede vacío; PDFs de planos sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier` responde muy lento (>30 s); `/board` accesible pero vacío.
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 6 entradas en CSV).
