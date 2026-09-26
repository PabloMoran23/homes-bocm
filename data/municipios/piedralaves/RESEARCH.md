# Piedralaves — investigación portal ayuntamiento

**Municipio:** Piedralaves (Castilla y León, Ávila)  
**INE:** 05187  
**Fecha:** 2026-08-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Urbimedia/Drupal) | https://www.piedralaves.es | Portal activo |
| Normas urbanísticas | https://www.piedralaves.es/normas-urbanisticas-de-piedralaves | NUM 2002, textos/planos PDF, modificación puntual |
| Trámites y solicitudes | https://www.piedralaves.es/ayuntamiento/tramites-solicitudes | Enlace a catálogo sede |
| Sede electrónica (espublico gestiona) | https://piedralaves.sedelectronica.es/board | Tablón de anuncios (~10 filas) |
| Catálogo trámites | https://piedralaves.sedelectronica.es/info | Destacados: licencia urbanística, instancia general |
| PLAI / PlanPublica JCYL | https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=281043 | Índice NUM vía WFS |
| SIUR visor CyL | https://idecyl.jcyl.es/siur/index.html?id=05187 | Visor cartográfico regional |

## Cómo se listan expedientes

- **Web Drupal:** página de normas urbanísticas con PDFs estáticos en `/sites/default/files/documentos/` (textos, planos, modificaciones).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Mezcla empleo, presupuesto y urbanismo (declaraciones de ruina, BOCYL).
- **PLAI:** `c_mun=05187`; documento principal accesible vía `url_doc_info` del WFS (cDocId 281043).
- **Sin visor municipal** de expedientes urbanísticos ni API JSON histórica en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Catálogo sede destaca «Solicitud de Licencia o Autorización Urbanística» e «Instancia General» (páginas informativas).
- Web enlaza modelos de instancia en sede; sin listado de licencias concedidas.
- Tablón puede incluir procedimientos urbanísticos (ruina) pero no concesiones sistemáticas de licencias de obra.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia/autorización.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Piedralaves'`
  - 1 instrumento (NUM 2002), 47 sectores (S.U., S.U.N.C., etc.), 1 plan parcial con polígonos MultiPolygon
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer PDFs web/tablón con polígono del instrumento NUM cuando aplica.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría individual.
  - Licencias de obra sin georreferencia.
  - `/dossier` y `/info` responden con redirección en bucle (302); solo `/board` scrapeable de forma estable.
  - Certificado sede puede requerir `insecure_ssl` en algunos entornos.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/planes), no licencias individuales.

## Limitaciones generales

- Municipio ~2.000 hab. en comarca del Alto Tiétar (Ávila).
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 3 entradas en CSV).
- 8 modificaciones puntuales a las NUM documentadas en web (solo una PDF enlazada directamente).
- Volumen bajo de publicaciones urbanísticas activas en tablón.
