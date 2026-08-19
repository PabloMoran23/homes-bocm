# Abades — investigación portal ayuntamiento

**Municipio:** Abades (Castilla y León, Segovia)  
**Fecha:** 2026-08-09

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Diputación Segovia) | https://www.abades.es | Portal Segovia8 theme (Diputación de Segovia) |
| Urbanismo | https://www.abades.es/urbanismo | Normas urbanísticas municipales: ~86 PDFs en biblioteca documental Liferay (memoria, planos, normativa, fichas, catálogo) |
| Actualidad municipal | https://www.abades.es/actualdiad-municipal | Noticias (Asset Publisher); proyecto renovación alumbrado público |
| Sede electrónica | https://abades.sedelectronica.es | Transparencia (normativa municipal, plenos); sin tablón `/board` espublico |
| Transparencia normativa | https://abades.sedelectronica.es/transparency/84f70440-174b-453a-9160-c05693aaf0a8/ | Normativa municipal |
| PLAI Junta CYL (prov. 40, mun. 001) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=001 | Archivo planeamiento aprobado |

## Cómo se listan expedientes

- **Liferay document library** en `/urbanismo`: carpetas colapsables (Memoria, Normativa, Planos, Catálogo, Fichas actuaciones aisladas, etc.) con enlaces directos a `/documents/1551391/<uuid>`.
- **Noticias** vía Asset Publisher en actualidad municipal (p. ej. proyecto renovación alumbrado PR-D5000-2021-001806).
- **Sin visor de expedientes** ni API JSON de listado histórico en sede.
- **Sede** (plataforma transparencia, no espublico gestiona): sin tablón de anuncios urbanísticos scrapeable; solo transparencia normativa y plenos.
- **BOCYL:** 5 entradas en CSV regional (`boletin_source_id: bocyl`).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra publicadas.
- Formularios PDF en urbanismo: `licencia de obra`, `licencia de primera ocupación`.
- Sede permite trámites con certificado digital; no hay listado público de concesiones.
- Estrategia adapter: páginas informativas de trámites (formularios PDF) + sede electrónica.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1), `urbanismo:plau_cyl_planes_parciales` (2), `urbanismo:plau_cyl_sectores` (16)
  - Filtro: `n_mun = 'Abades'`
  - Campos: `n_titulo`, `n_sector`, `n_num_sect`, `c_id_sect`, `f_aprob`, `f_bocyl`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas Liferay por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Sede sin tablón público de anuncios urbanísticos.
  - PDFs de normativa/planos sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Sede electrónica responde lento o vacía desde CI; no requiere `insecure_ssl`.
- Municipio muy pequeño (~300 hab.); volumen bajo de publicaciones urbanísticas activas.
- Portal gestionado por plantilla Diputación de Segovia (Liferay); patrón replicable en otros municipios segovianos.
