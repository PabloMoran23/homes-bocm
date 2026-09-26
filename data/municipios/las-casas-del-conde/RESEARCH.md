# Las Casas del Conde — investigación portal ayuntamiento

**Municipio:** Las Casas del Conde (Castilla y León, Salamanca)  
**INE:** 37090 (provincia 37, municipio 090)  
**Fecha:** 2026-08-30

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.lascasasdelconde.com/ | Página estática mínima (imagen turismo, sin sección urbanismo) |
| Sede electrónica (espublico gestiona) | https://lascasasdelconde.sedelectronica.es | Portal principal de trámites y transparencia |
| Tablón de anuncios | https://lascasasdelconde.sedelectronica.es/board | Vacío («No se han encontrado elementos») |
| Catálogo de trámites | https://lascasasdelconde.sedelectronica.es/dossier | Trámites genéricos (instancia general, quejas, padrón) |
| Transparencia | https://lascasasdelconde.sedelectronica.es/transparency | Gobierno abierto |
| PLAU JCyL (archivo aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=37&municipio=090 | Documentación planeamiento aprobado |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | Capas PLAU CyL georreferenciadas |

## Cómo se listan expedientes

- **Sin visor de expedientes** ni listado HTML de planeamiento en la sede.
- **Tablón espublico:** vacío en el momento de la investigación; sin anuncios de información pública ni licencias.
- **PLAU JCyL:** documentación de planeamiento aprobado (índice por municipio).
- **IDECyL WFS:** 1 instrumento de planeamiento con geometría (`DELIMITACIÓN DE SUELO URBANO SIN ORDENANZAS`, aprobado 1976).
- **BOCYL:** publicaciones puntuales (p. ej. declaración de ruina calle Parrales 15, 2018) — ya en `projects.json` regional.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en tablón ni datos abiertos.
- La sede no expone catálogo de trámites de urbanismo/licencias de obra.
- Estrategia adapter: páginas informativas (tablón, dossier, transparencia) como referencia de trámite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'Las Casas del Conde'`
  - Resultado: 1 instrumento (DSU) con `MultiPolygon` en EPSG:4326; 0 sectores ni planes parciales
  - Campo enlace: `url_doc_info` → documento PLAU CyL
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer fila PLAU por coincidencia de título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría individual.
  - Municipio pequeño (~100 hab.) con planeamiento histórico (DSU 1976) sin sectores actuales.
  - Licencias de obra sin georreferencia pública.
  - Certificado SSL de la sede inválido (`insecure_ssl` en manifest).

## Limitaciones generales

- Web corporativa sin contenido de urbanismo; toda la administración vía sede espublico.
- Tablón de anuncios vacío.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).
- SSL de `lascasasdelconde.sedelectronica.es` no verifica en entornos CI — requiere `insecure_ssl: true`.
