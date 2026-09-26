# Milagros — investigación portal ayuntamiento

**Municipio:** Milagros (Burgos, Castilla y León)  
**INE:** `09218` (provincia `09`, municipio `218`)  
**BOCYL:** `bocyl` (1 publicación en cola)

## URLs base y páginas semilla

| Fuente | URL | Tecnología | Contenido urbanístico |
|--------|-----|------------|----------------------|
| Web corporativa | https://www.milagros.es | Drupal (tema Toools Dip. Burgos) | Noticias (`/noticias`, `/noticia/*`); sin sección urbanismo dedicada |
| Información general | https://www.milagros.es/informacion-general | Drupal | Enlace al archivo PLAU JCyL |
| Sede electrónica | https://milagros.sedelectronica.es | espublico gestiona (Wicket) | Tablón `/board/` vacío; trámites `/dossier` (~114 procedimientos) |
| PlanPublica JCyL | `servicios.jcyl.es/PlanPublica` prov=09 mun=218 | JSP | 4 documentos PLAU (PP, NUM, NS) |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/ows` | GeoServer WFS | Instrumentos, plan parcial SUI-2, 12 sectores |

## Expedientes / proyectos

- **Tablón sede:** sin filas publicadas (tbody vacío, sept 2026).
- **PlanPublica:** documentos aprobados (plan parcial 2008, NUM 2012, NS 2016, etc.) vía `openDocumento.do?cDocId=…`.
- **IDECyL WFS:** capas `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_planes_parciales` (1 PP SUI-2 exp. 141/06W), `plau_cyl_sectores` (12 sectores SU-NC/SUR).
- **Noticias Drupal:** pocas entradas; sin urbanismo reciente en listado.

## Licencias

- **Tablón:** vacío; no hay concesiones publicadas.
- **Trámites sede (`/dossier`):** catálogo espublico con procedimientos estándar (licencia urbanística, comunicación previa, DR, etc.) — páginas informativas, no concesiones.
- Estrategia adapter: devolver trámites de licencia del catálogo como filas informativas (`min_rows: 0` en validación de licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
  - Filtro: `CQL_FILTER=c_mun='09218'`, `srsName=EPSG:4326`
  - Campo enlace: `url_doc_info`, `c_id_sect`, `n_num_sect`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por código de sector en títulos PlanPublica/WFS.
- **Limitaciones:** tablón sin PDFs georreferenciables; licencias sin coordenadas; sectores WFS sin `url_doc_info` individual.

## Limitaciones

- `/dossier` responde lento (~3–12 s); requiere cookie jar y timeout 90 s.
- Tablón de anuncios sin publicaciones urbanísticas.
- Web Toools sin visor urbanístico propio; geometría solo vía IDECyL.
- PlanPublica usa código interno municipio `218` (no INE completo).
