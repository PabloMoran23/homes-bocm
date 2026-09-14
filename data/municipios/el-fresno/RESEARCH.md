# El Fresno — investigación portal ayuntamiento

**Municipio:** El Fresno (Castilla y León, Ávila)  
**Fecha:** 2026-09-14

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (plantilla Diputación de Ávila) | https://www.elfresno.es | CMS estático DipuÁvila 2020-0.2b |
| Normas urbanísticas | https://www.elfresno.es/ayuntamiento/normas-urbanisticas/ | Enlace a PLAU JCyL |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=05&municipio=076 | Archivo planeamiento vigente (cód. municipio 076) |
| PLAU print | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlauPrint.do?provincia=05&municipio=076&bInfoPublica=N | 3 documentos NUM (modificaciones 2010 y 2024) |
| Sede electrónica (espublico gestiona) | https://elfresno.sedelectronica.es/board/ | Tablón de anuncios (~3 filas; sin urbanismo) |
| Sede trámites | https://elfresno.sedelectronica.es/dossier/.0 | Catálogo de trámites |
| Sede info | https://elfresno.sedelectronica.es/info.0 | Tablón informativo (vacío en prueba) |

## Cómo se listan expedientes

- **Web DipuÁvila:** sección `/ayuntamiento/normas-urbanisticas/` con ficha PLAU que enlaza al visor JCyL (`provincia=05&municipio=076`). Sin PDFs locales de planeamiento.
- **PLAU CyL:** consulta pública HTML con `doOpen(docId, codigo)`; versión print scrapeable con título, instrumento y fechas.
- **Tablón sede:** HTML espublico estándar (`preview-document`); 3 anuncios (bando locales, contenedores, pago proveedores) sin contenido urbanístico.
- **Sin visor de expedientes** municipal ni API JSON de información pública.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- El catálogo de trámites (`/dossier/.0`) incluye solicitudes de licencia urbanística de forma informativa.
- Estrategia adapter: páginas informativas de sede (tablón + dossier) + tablón si aparecen anuncios de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'El Fresno'`
  - Resultado: 1 instrumento (NUM) + 11 sectores con `MultiPolygon`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer fichas PLAU/web por coincidencia de título o sector.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia en portal.
  - Tablón sede sin anuncios de urbanismo.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Plantilla DipuÁvila sin REST API; scrape HTML determinista.
- Sede `/dossier/.0` puede responder lento (>30 s).
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
