# Onzonilla y Vega de Infanzones (León, Castilla y León)

## Contexto BOCM

El slug `onzonilla-y-vega-de-infanzones` agrupa en la cola un aviso BOCYL que referencia **dos entidades locales** del mismo entorno (León): el ayuntamiento de **Onzonilla** (INE 24120) y el municipio de **Vega de Infanzones** (INE 24197), sin sede web independiente.

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal (OpenCms) | https://www.aytoonzonilla.es |
| Sede electrónica (espublico) | https://ayuntamientodeonzonilla.sedelectronica.es |
| Tablón de anuncios | https://ayuntamientodeonzonilla.sedelectronica.es/board |
| Tablón información pública | https://ayuntamientodeonzonilla.sedelectronica.es/info |
| Catálogo trámites (dossier) | https://ayuntamientodeonzonilla.sedelectronica.es/dossier |
| Trámites licencias (web) | `/ayuntamiento/tramites-solicitudes/licencias-urbanisticas-ambientales-apertura/` |
| PlanPublica Onzonilla (prov 24, mun 120) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=120 |
| PlanPublica Vega de Infanzones (mun 197) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=197 |

**Nota sede:** `onzonilla.sedelectronica.es` responde «Sede Indeterminada»; el host válido es `ayuntamientodeonzonilla.sedelectronica.es` (enlace desde la portada municipal).

## Expedientes / proyectos

- **Tablón espublico:** listado HTML con enlaces `preview-document/{uuid}`; columnas expediente, procedimiento, categoría (Urbanismo), descripción y fecha.
- **PlanPublica JCyl:** listados AJAX de documentos de planeamiento (información pública y archivo) para Onzonilla y Vega de Infanzones.
- **IDECyL WFS** (`urbanismo` GeoServer): capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun` ∈ {Onzonilla, Vega de Infanzones}; geometría en GeoJSON con `srsName=EPSG:4326`.

## Licencias de obra

- No hay dataset de concesiones en datos abiertos.
- Tablón: anuncios puntuales si categoría/procedimiento menciona licencia u obra.
- Páginas informativas de trámites en la web OpenCms y catálogo `catalog/t/...` en dossier (mismo patrón que otros ayuntamientos Samdipu León).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Onzonilla'` o `'Vega de Infanzones'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Campos útiles: `n_num_sect`, `c_id_sect`, `url_doc_info`
- **Estrategia:** ingestar features WFS como filas de proyecto con `geom_geojson`; enriquecer anuncios del tablón que citen códigos S.U.N.C./SU-NC vía query puntual a `plau_cyl_sectores`.
- **Limitaciones:** no hay visor ArcGIS municipal; expedientes del tablón suelen ser PDF sin georreferencia; Vega de Infanzones solo aporta geometría vía capas autonómicas, no portal propio.

## Limitaciones generales

- Normativa urbanística en ruta OpenCms `/normativa-municipal/urbanismo/` devuelve 404 (contenido movido o retirado).
- SSL de sede: adapter usa `insecure_ssl: true` (patrón CYL espublico).
- Paginación del tablón limitada a la primera página visible en HTML estático.
