# La Colilla — investigación portal ayuntamiento

**Municipio:** La Colilla (Castilla y León, Ávila)  
**Fecha:** 2026-08-29

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.lacolilla.es | CMS estático DipuÁvila 2020 |
| Normas urbanísticas | https://www.lacolilla.es/ayuntamiento/normas-urbanisticas/ | Enlace a archivo PLAU CyL |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=061 | Archivo planeamiento vigente (cód. municipio 061, INE 05061) |
| Tablón web municipal | https://www.lacolilla.es/ayuntamiento/tablon-de-anuncios/ | 2 anuncios (subvenciones MOVES III, instalaciones eléctricas) |
| Sede electrónica (espublico gestiona) | https://lacolilla.sedelectronica.es/board | Tablón de anuncios (5 filas: bandos fiscales, ordenanzas agua, jurado) |
| Sede trámites | https://lacolilla.sedelectronica.es/dossier | Catálogo de trámites (lento; sin filas urbanismo visibles en prueba) |
| Sede inicio | https://lacolilla.sedelectronica.es/info | Redirige desde raíz sede |

## Cómo se listan expedientes

- **Web DipuÁvila:** sección `/ayuntamiento/normas-urbanisticas/` con ficha única «PLAU - Junta de Castilla y León» que enlaza al buscador JCyL. No hay listado local de modificaciones ni PDFs de sectores en la web municipal.
- **PLAU CyL:** consulta pública por código provincia/municipio (05/061); 4 documentos de planeamiento en archivo regional.
- **Tablón sede:** HTML espublico estándar (`preview-document`); filas actuales son bandos fiscales y ordenanzas, sin categoría urbanismo.
- **Sin visor de expedientes** ni listado JSON de información pública en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- El tablón sede no expone licencias de obra; solo avisos administrativos.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios de licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'La Colilla'`
  - Resultado: 1 instrumento (NNSS) + 7 sectores con `MultiPolygon` (0 planes parciales)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer fichas web por coincidencia de sector en título si aparecen.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia en portal.
  - Web municipal sin PDFs de planos locales.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier` responde muy lento (>60 s); `/board` accesible con anuncios no urbanísticos.
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).
