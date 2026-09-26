# Riofrío de Riaza — investigación portal ayuntamiento

**Municipio:** Riofrío de Riaza (Castilla y León, Segovia)  
**Fecha:** 2026-08-22

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Diputación Segovia) | https://www.riofrioderiaza.es | Portal Segovia8 theme gestionado por Diputación de Segovia |
| Actualidad municipal | https://www.riofrioderiaza.es/actualdiad-municipal | Noticias (Asset Publisher); sin urbanismo reciente |
| Publicaciones oficiales | https://www.riofrioderiaza.es/publicaciones-oficiales | Bandos y publicaciones oficiales |
| Normativa municipal | https://www.riofrioderiaza.es/normativa-municipal | Normativa local |
| Vivienda | https://www.riofrioderiaza.es/vivienda | Información vivienda y trámites relacionados |
| Área de descargas | https://www.riofrioderiaza.es/area-de-descargas | Galería documental Liferay |
| Sede electrónica (espublico gestiona) | https://riofrioderiaza.sedelectronica.es | Tablón `/board` (vacío), catálogo `/dossier`, consulta expedientes |
| PLAI Junta CYL (prov. 40, mun. 172) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=172 | Archivo planeamiento (sin documentos publicados) |

**No existe** sección `/urbanismo` en la web municipal (HTTP 404). Ni en portal DipSegovia.

## Cómo se listan expedientes

- **Sin visor de expedientes urbanísticos** en la web corporativa.
- **Sede espublico:** tablón de anuncios `/board` responde pero sin filas urbanísticas (solo cabecera de tabla).
- **Consulta expedientes** en sede (`/expedientes`) requiere login o búsqueda puntual; no hay listado público scrapeable de planeamiento.
- **PLAI JCYL:** sin documentos de planeamiento aprobado ni en información pública para mun. 172.
- **IDECyL WFS:** un registro `SIN PLANEAMIENTO GENERAL` (ámbito municipal completo).
- **BOCYL:** 3 entradas en CSV regional (`boletin_source_id: bocyl`).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra publicadas.
- Trámites disponibles vía sede `/dossier` (catálogo espublico) y página `/vivienda`.
- No hay tablón con licencias concedidas.
- Estrategia adapter: páginas informativas de trámites (vivienda, sede dossier/board) + formularios PDF si aparecen en Liferay.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capa: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: ámbito municipal sin PGOU)
  - Filtro: `n_mun = 'Riofrío de Riaza'`
  - Geometría: `MultiPolygon` en EPSG:4326 (delimitación municipal / ámbito sin planeamiento)
- **Estrategia:** ingestar feature WFS como proyecto con `geom_geojson`; enriquecer otras filas por coincidencia de título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni WFS de sectores/parciales (0 features en otras capas).
  - Licencias sin georreferencia.
  - Tablón sede vacío.
  - Municipio pequeño (~150 hab.) sin PGOU aprobado.

## Limitaciones generales

- Sede `/dossier` responde lento (~45–90 s); adapter usa timeout extendido e `insecure_ssl`.
- Portal Liferay sin sección urbanismo; patrón Segovia8 replicable en municipios segovianos pequeños.
- Sin datos abiertos georreferenciados locales; solo IDECyL regional.
