# Remondo — investigación portal ayuntamiento

**Municipio:** Remondo (Castilla y León, Segovia)  
**Fecha:** 2026-10-14

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Diputación Segovia) | https://www.remondo.es | Portal Segovia8; título «dipsegovia.es» en metadatos |
| Urbanismo | https://www.remondo.es/urbanismo | Sección urbanismo (documentos Liferay si existen) |
| Actualidad municipal | https://www.remondo.es/actualdiad-municipal | Asset Publisher: IP de autorizaciones de uso (suelo urbanizable/rústico/urbano), telecomunicaciones, vivienda |
| Sede electrónica (espublico) | https://remondo.sedelectronica.es | Redirige a `/info`; tablón `/board` sin `preview-document` activos |
| Catálogo trámites | https://remondo.sedelectronica.es/dossier | Trámites con certificado (sin listado histórico de concesiones) |
| PLAI Junta CYL (prov. 40, mun. **166**) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=166 | Archivo NUM y modificaciones (7 documentos) |
| PLAI en IP | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=166 | Planeamiento en información pública |
| SIUR IDECyL | https://idecyl.jcyl.es/siur/index.html?id=40167 | Visor regional planeamiento (INE 40167) |

## Cómo se listan expedientes

- **PLAI JCyL:** tabla HTML con `doOpenDocumento` / fechas de aprobación y títulos (NUM, modificaciones puntuales).
- **Actualidad Liferay:** tarjetas con título + descripción (expediente en texto libre, p. ej. «Expte.: 155/2025»).
- **Sede espublico:** tablón accesible pero vacío de anuncios urbanísticos en el momento de la investigación.
- **Sin API JSON** ni visor municipal de expedientes enlazado a geometría.

## Cómo se publican licencias

- No hay dataset público de licencias de obra concedidas.
- Las autorizaciones de uso / IP en actualidad municipal se tratan como **proyectos/actuaciones** (no concesiones con fecha).
- Estrategia adapter: páginas informativas de trámites en sede + formularios si aparecen en urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS OWS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'Remondo'`
  - SIUR: visor web sin API directa por expediente; referencia para humanos
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; intentar cruce por nombre de sector en títulos Liferay/PLAI.
- **Limitaciones:**
  - Anuncios de IP en Liferay sin polígono asociado.
  - Tablón sede sin geometría.
  - WFS con cobertura PLAU CyL (instrumentos/sectores), no licencias puntuales.

## Limitaciones generales

- `www.dipsegovia.es/web/ayuntamiento-de-remondo` no responde de forma fiable desde el entorno del agente; se usa `www.remondo.es`.
- Municipio pequeño; volumen bajo pero PLAI NUM histórica rica.
- BOCYL: 1 entrada en cola regional (`boletin_source_id: bocyl`).
