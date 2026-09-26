# La Horra — investigación portal ayuntamiento

**Municipio:** La Horra (Castilla y León, Burgos)  
**Fecha:** 2026-09-20

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Drupal 10) | https://www.lahorra.es | Portal activo |
| Información general / planeamiento | https://www.lahorra.es/pagina-basica/informacion-general | Enlace al archivo PlanPublica JCyL |
| Sede electrónica (espublico gestiona) | https://lahorra.sedelectronica.es | Trámites y tablón de anuncios |
| Tablón sede | https://lahorra.sedelectronica.es/board | 6 anuncios (2 urbanismo EDAR BALBAS, resto ordenanzas/padrón) |
| PlanPublica JCyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=168 | 8 documentos (NS + revisiones PGOU) |
| SIUR / mapa planeamiento | https://idecyl.jcyl.es/siur/index.html?id=09168 | Visor cartográfico JCyL (INE 09168) |

## Cómo se listan expedientes

- **Drupal:** página de información general con enlace al archivo PlanPublica JCyL. Sin listado propio de expedientes ni PDFs de urbanismo en la web municipal.
- **PlanPublica JCyL:** tabla HTML con `doGoBoletin(docId, codigo)` — 8 documentos vigentes (Normas Subsidiarias de Planeamiento Municipal y revisiones PGOU 2003–2014).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Incluye 2 anuncios de información pública / licencia urbanística (EDAR BALBAS SL, expediente 117/2026).
- **Sin visor municipal** de expedientes individuales ni API JSON del ayuntamiento.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Trámites de licencia accesibles vía sede `/dossier` (catálogo espublico).
- Tablón publica solicitudes de licencia urbanística en trámite (EDAR BALBAS).
- Estrategia adapter: páginas informativas de trámites + tablón (filas licencia) + anuncios urbanísticos del tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM), `urbanismo:plau_cyl_sectores` (2 sectores U.A. 2 y U.A. 3), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'La Horra'`
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=09168`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer documentos PlanPublica por coincidencia de nombre en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede.
  - Licencias de obra sin georreferencia (solo anuncios tablón).
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.

## Limitaciones generales

- Web municipal mínima en urbanismo (solo enlace a JCyL).
- Certificado sede válido; no requiere `insecure_ssl`.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 1 entrada en CSV).
