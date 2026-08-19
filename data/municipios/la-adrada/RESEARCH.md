# La Adrada — investigación portal ayuntamiento

**Municipio:** La Adrada (Castilla y León, Ávila)  
**Fecha:** 2026-08-13

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress + Elementor) | https://www.laadrada.es | Portal activo |
| Urbanismo | https://www.laadrada.es/urbanismo/ | Enlaces a mapa SIUR y listado PlanPublica JCyL |
| Sede electrónica (espublico gestiona) | https://adrada.sedelectronica.es | Trámites y tablón de anuncios |
| Tablón sede | https://adrada.sedelectronica.es/board | 4 anuncios visibles (pleno, certificados, ordenanza) |
| PlanPublica JCyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=002 | 3 documentos de planeamiento |
| SIUR / mapa planeamiento | https://idecyl.jcyl.es/siur/index.html?id=05002 | Visor cartográfico JCyL (INE 05002) |
| WP REST API | https://www.laadrada.es/wp-json/wp/v2 | pages/posts |

## Cómo se listan expedientes

- **WordPress:** página `/urbanismo/` con botones MAPA (SIUR) y Listado (PlanPublica). Sin PDFs ni listado propio de expedientes.
- **PlanPublica JCyL:** tabla HTML con `doOpen(docId, codigo)` — 3 documentos vigentes (estudio de detalle Las Moreras, plan parcial sector E Camino de la Picota, convenio urbanístico CT eléctricos).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Sin filas de urbanismo en el momento de la investigación.
- **Sin visor municipal** de expedientes individuales ni API JSON del ayuntamiento.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Trámites de licencia accesibles vía sede `/dossier` (catálogo espublico).
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM), `urbanismo:plau_cyl_sectores` (66 sectores), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'La Adrada'`
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=05002`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer documentos PlanPublica por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede.
  - Licencias de obra sin georreferencia.
  - Tablón sede sin anuncios urbanísticos recientes.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Web municipal mínima en urbanismo (solo enlaces a JCyL).
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 4 entradas en CSV).
