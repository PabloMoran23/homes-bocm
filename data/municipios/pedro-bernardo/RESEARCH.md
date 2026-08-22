# Pedro Bernardo — investigación portal ayuntamiento

**Municipio:** Pedro Bernardo (Castilla y León, Ávila)  
**Fecha:** 2026-08-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Interportal 3.0) | http://www.pedrobernardo.es/ | En mantenimiento («Trabajando») — sin sección urbanismo accesible |
| Sede electrónica (espublico gestiona) | https://pedrobernardo.sedelectronica.es | Trámites, tablón, transparencia |
| Tablón sede | https://pedrobernardo.sedelectronica.es/board | 2 anuncios (IAE cobranza, calendario fiscal) — sin urbanismo |
| Trámites | https://pedrobernardo.sedelectronica.es/dossier | Catálogo espublico (licencias vía trámite, sin listado de concesiones) |
| Transparencia | https://pedrobernardo.sedelectronica.es/transparency | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (29 documentos, Wicket AJAX) |
| PlanPublica JCyL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=182 | Sin documentos vigentes en listado impreso |
| PlanPublica JCyL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=05&municipio=182 | Sin documentos en tramitación |
| SIUR / mapa planeamiento | https://idecyl.jcyl.es/siur/index.html?id=05182 | Visor cartográfico JCyL (INE 05182) |
| IDECyL WFS | https://idecyl.jcyl.es/geoserver/urbanismo/ows | Capas PLAU CyL con geometría |

## Cómo se listan expedientes

- **Web municipal:** inaccesible (página de mantenimiento).
- **PlanPublica JCyL:** catálogo provincial sin filas `doOpen` para este municipio en aprobado ni info pública; el instrumento NS figura en WFS con enlace `url_doc_info`.
- **IDECyL WFS:** GeoJSON con metadatos (`n_titulo`, `c_plan`, `f_bocyl`, `url_doc_info`):
  - 1 instrumento: Normas Subsidiarias de Planeamiento Municipal (NS, aprob. 1996)
  - 1 plan parcial: «Balcón del Tiétar» exp. 77/05 (aprob. 2006)
  - 5 sectores (S-1 … S-5)
- **Tablón sede:** HTML tabla espublico con `preview-document`; sin filas de urbanismo.
- **Transparencia:** árbol Wicket con 29 docs en urbanismo (requiere sesión AJAX para descarga individual).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni sede.
- Trámites de licencia accesibles vía sede `/dossier` (catálogo espublico).
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NS), `urbanismo:plau_cyl_planes_parciales` (1 PP), `urbanismo:plau_cyl_sectores` (5)
  - Filtro: `n_mun = 'Pedro Bernardo'`
  - Visor SIUR: `https://idecyl.jcyl.es/siur/index.html?id=05182`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson` en EPSG:4326; enriquecer documentos PlanPublica por coincidencia de nombre si aparecen.
- **Limitaciones:**
  - Web corporativa en mantenimiento.
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede.
  - Licencias de obra sin georreferencia.
  - Tablón sede sin anuncios urbanísticos.
  - Geometría WFS solo para ámbitos PLAU CyL, no licencias individuales.
  - Certificado sede con cadena intermedia; adapter usa `insecure_ssl`.

## Limitaciones generales

- Municipio pequeño (~900 hab.) con planeamiento centralizado en JCyL (PLAU CyL).
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 3 entradas en CSV).
- NUM (Normas Urbanísticas Municipales) aprobadas provisionalmente en 2010 con tramitación interrumpida (BOCyL 4/06/2010) — no figuran en WFS vigente.
