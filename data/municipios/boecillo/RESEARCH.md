# Boecillo — investigación portal ayuntamiento

**Municipio:** Boecillo (Valladolid, Castilla y León)  
**INE:** 47023  
**Fecha:** 2026-08-15  
**BOCYL regional (referencia):** 3 avisos

## Resumen

Boecillo combina web corporativa WordPress (`www.boecillo.es`) con sede electrónica **espublico gestiona**
(`boecillo.sedelectronica.es`). El planeamiento histórico está en **PLAI JCYL** (municipio 023, provincia 47)
y la cartografía sectorial en **IDECyL WFS**. La página de urbanismo enlaza visores de la Diputación de Valladolid
(LocalGIS, UER, IDEVALL).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.boecillo.es` | WordPress custom | Urbanismo, noticias IP licencias ambientales, plan parcial |
| Urbanismo | `https://www.boecillo.es/ayuntamiento/urbanismo/` | HTML | Enlaces a visores GIS diputación |
| Tablón sede | `https://boecillo.sedelectronica.es/board` | HTML Wicket | Edictos recientes (~9 filas visibles) |
| Trámites sede | `https://boecillo.sedelectronica.es/dossier` | HTML Wicket | Catálogo trámites (`/catalog/t/{uuid}`) |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (mun. 023, prov. 47) | HTML tabla | Planes parciales históricos, modificaciones PT |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | 23 sectores + planes parciales Boecillo |
| LocalGIS Dip. | `localgis.diputaciondevalladolid.es:8082/...idEntidad=6` | Visor web | Guía urbana municipal |
| UER | `uer.diputaciondevalladolid.es/Boecillo/` | Visor web | Urbanismo en red |
| IDEVALL | `idevall.diputaciondevalladolid.es/visor/mapviewer.jsf` | Visor web | Datos locales Valladolid |

## Tablón de anuncios (`/board`)

Enlaces `preview-document/{uuid}` a PDF. En la muestra actual predominan ordenanzas fiscales y contratación;
aparece exposición pública de proyecto de obras (patio nave municipal). Urbanismo esporádico en tablón.

## WordPress — noticias urbanísticas

REST API pública (`/wp-json/wp/v2/posts`). Contenido relevante:

- Múltiples entradas «información pública en expediente de solicitud de licencia ambiental» (industrial/fotovoltaica)
- Aprobación inicial plan parcial sector 18 (2022)
- Edictos BOPVA / disposiciones urbanísticas (2013)

## PLAI JCYL

Código municipio PLAI: **023** (provincia 47, INE 47023). Documentos incluyen:

- PP SECTOR INDUSTRIAL RECINTO 3 PARQUE TECNOLÓGICO DE BOECILLO
- Modificaciones puntual PP PARQUE TECNOLÓGICO LAS ARROYADAS
- PP EL MORAL, LA BARCA, EL PEREGRINO, sectores residenciales
- PP EL FILLO y otros instrumentos históricos

## Licencias

No hay visor georreferenciado municipal de concesiones de obra (sin paridad Madrid DROUS).

- Tablón y noticias WP publican licencias ambientales / información pública
- Página urbanismo describe tramitación de licencias de obra
- Catálogo sede aporta trámites informativos

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 23 polígonos (SECTOR UB 1–25, SECTOR IND, SURND/SN 01, etc.)
  - WFS `urbanismo:plau_cyl_planes_parciales` — planes parciales Boecillo
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — ámbito instrumento
  - Filtro: `n_mun ILIKE 'Boecillo%'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Visor SIUCyL: `https://idecyl.jcyl.es/siur/` (sin enlace directo a expediente)
  - LocalGIS Diputación (`idEntidad=6`) — visor cartográfico sin API pública de expedientes
- **Estrategia:** ingestar capas WFS como proyectos con `geom_geojson`; enriquecer filas PLAI/tablón/WP
  por coincidencia de nombre de sector en título (SECTOR 18, PARQUE TECNOLÓGICO, etc.)
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia ambiental
  - LocalGIS/IDEVALL no exponen query REST por expediente sin sesión
  - PLAI no expone coordenadas; solo PDF/BOCYL
  - Botones «planeamiento en información pública» en WP urbanismo apuntan a `#` (sin URL)

## Limitaciones generales

- Tablón sede muestra pocas filas urbanísticas en muestra actual
- Dossier sede puede tardar en CI (CookieJar + `insecure_ssl`)
- Licencias de obra: solo trámites informativos, no listado de concesiones
