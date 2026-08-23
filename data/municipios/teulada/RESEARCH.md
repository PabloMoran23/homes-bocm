# Teulada — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `teulada` |
| INE | 03101 |
| Provincia | Alicante / Comunitat Valenciana |
| Boletín | DOGV (`dogv`, 3 entradas BOCM) |

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.teuladamoraira.com.es | CMS Woden (Insyde/Geonet) |
| Sede electrónica | https://teuladamoraira.sedelectronica.es | espublico gestiona (Wicket/YUI) |
| Tablón de anuncios | https://teuladamoraira.sedelectronica.es/board | Edictos y anuncios públicos |
| Portal transparencia | https://teuladamoraira.sedelectronica.es/transparency/ | Sección 7 — Urbanismo (276 docs) |
| Área Urbanismo (web) | https://www.teuladamoraira.com.es/attm/Web_php/index.php?contenido=subapartados_woden&id_boto=43 | Área municipal sin listado de expedientes |
| Geoportal | https://geoportal.teuladamoraira.org | Launcher Geonet; visor en visorteulada.geonet.es |
| Agenda Urbana | https://agendaurbanateuladamoraira.es | WordPress/Divi — participación y documentación AU |
| Catálogo trámites | https://teuladamoraira.sedelectronica.es/dossier | Licencias vía sede (sin histórico público) |

## Cómo se listan expedientes / proyectos

1. **ICV WFS InventarioSuSuz:** 75 sectores SU/SUZ aprobados para INE 03101 con polígonos en GML3.
2. **Tablón `/board`:** tabla HTML espublico (`class_name`, `class_folderCode`, `preview-document/{uuid}`). En la investigación predominan anuncios de empleo público; filas urbanísticas puntuales.
3. **Portal transparencia:** carpeta «7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» con 276 documentos cargados vía **Wicket AJAX** (no listado HTML estático).
4. **Geoportal Geonet:** `frames.json` expone capas de urbanismo (PGOU, clasificación, zonificación) y «Expedientes Municipales (Gestiona)» (layer 2710) en visor iframe; sin API REST pública enlazable a código de expediente.

## Cómo se publican licencias

- No hay listado público histórico de licencias concedidas en la web municipal.
- El tablón sede publica edictos puntuales; en el momento de la investigación no había licencias de obra activas (mayoría empleo público).
- Trámites de licencia vía sede (`/dossier`) y consulta de expedientes (`/expedientes`, requiere identificación).
- Área «Licencias de actividad» en web (`id_boto=4468`) sin histórico indexable.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento/ows`
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Filtro en cliente: `cod_ine_mun=03101` (75 polígonos)
  - Geoportal Geonet: `https://visorteulada.geonet.es/` (idApp=102); capas PGOU (787, 1157, 1164) y expedientes Gestiona (2710) — visor iframe sin REST query pública
- **Estrategia:** descargar WFS paginado, convertir `posList` GML → GeoJSON Polygon WGS84; enriquecer filas tablón/transparencia por coincidencia de título.
- **Limitaciones:**
  - WFS no admite `CQL_FILTER` fiable ni `application/json`; solo GML3.
  - Visor Geonet (expedientes municipales) no expone ArcGIS REST query enlazable desde CI.
  - Portal transparencia con 276 docs requiere sesión AJAX Wicket.
  - Licencias del tablón son PDFs sin georreferencia.

## Limitaciones generales

- Web municipal lenta en CI (timeouts ocasionales en subapartados Woden).
- Tablón actual mayoritariamente no urbanístico (selección de personal).
- Sede transparencia sin listado estático de documentos urbanísticos.

## Adapter

- `municipio.adapters.teulada:TeuladaAyuntamientoAdapter`
- Fuentes: ICV WFS + tablón sede + carpeta transparencia (metadatos) + geoportal/agenda urbana (informativos) + páginas trámites licencias.
