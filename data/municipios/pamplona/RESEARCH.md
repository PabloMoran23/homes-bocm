# Pamplona / Iruña — portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.pamplona.es |
| Actuaciones urbanísticas | https://www.pamplona.es/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas |
| Proyectos (redacción / terminados) | https://www.pamplona.es/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/proyectos |
| Obras (ejecución / terminadas) | https://www.pamplona.es/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/obras |
| Gestión de polígonos (PDFs reparcelación) | https://www.pamplona.es/temas/urbanismo-vivienda-e-infraestructuras/actuaciones-urbanisticas/gestion-poligonos |
| Plan municipal | https://www.pamplona.es/temas/urbanismo-vivienda-e-infraestructuras/plan-municipal |
| GeoPamplona (visor Ciudad) | https://sig.pamplona.es/ |
| Portal transparencia Gerencia Urbanismo | https://transparenciagerenciadeurbanismo.pamplona.es/ |
| Sede electrónica | https://sedeelectronica.pamplona.es |
| SIUN (instrumentos Navarra) | https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/instrumento/12856 |

## Cómo se listan expedientes / proyectos

- **CMS:** Drupal 10 (`ayuntamiento_theme`).
- **Proyectos y obras:** páginas tipo *cover* con listas `<li class="field--item"><a href="/slug-proyecto">…</a>`.
- **Detalle:** nodos con `field--name-body`, PDFs en `field--name-field-documents` y rutas `/sites/default/files/YYYY-MM/…`.
- **Gestión polígonos:** lista HTML con enlaces directos a PDFs de reparcelación / liquidación (sin ficha intermedia).
- **No hay** API JSON ni tablón de información pública indexable como Madrid/Getafe; el seguimiento de expedientes individuales es presencial/sede con certificado.

## Licencias de obra

- No se publica un listado de licencias concedidas (fechas, direcciones).
- Trámites informativos en sede:
  - Ejecución de obras y/o actividad clasificada: `FichaTramite.aspx?id=203404TA`
  - Obras menores — actuaciones comunicadas: `FichaTramite.aspx?id=58472TA`
  - Consultas urbanísticas: `id=20-41957`, `id=20-41967`
- El adapter ingiere estas fichas como filas informativas (`min_rows: 0` en licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoPamplona visor Ciudad: https://sig.pamplona.es/ — capa **Plan Municipal homologado** (`IDEN_Pol_Municipio` vía `uxogc/wms` y `uxogc/wfs`, EPSG:25830 en visor; export WGS84 en queries).
  - Enlace embebido desde plan municipal (visor preconfigurado con la misma capa).
  - IDENA (Gobierno de Navarra) aporta cartografía general y BTUNa Pamplona, pero **no** expone en WFS público la capa municipal de gestión del plan homologado (solo en SIG municipal).
- **Estrategia:** tras scrape, `_enrich_geometry` intenta `GetFeature` WFS en `sig.pamplona.es` y hace match por tokens del título (códigos ARS/ARZ, U.I., barrios). Si el host no responde (timeout en cloud), el orquestador usa centroide municipal + jitter.
- **Limitaciones:** sin enlace expediente↔`objectId` en el HTML Drupal; `sig.pamplona.es` puede no ser alcanzable desde todos los entornos; polígonos solo a nivel de ámbitos del plan, no por licencia.

## Limitaciones generales

- Sin tablón público de licencias.
- Transparencia Gerencia Urbanismo: portal aparte, lento / vacío en algunos entornos.
- PDFs grandes en gestión de polígonos; fechas inferidas de ruta `/sites/default/files/YYYY-MM/`.
