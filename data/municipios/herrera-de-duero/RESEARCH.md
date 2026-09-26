# Herrera de Duero — investigación portal ayuntamiento

**Entidad:** Herrera de Duero (pedanía de Tudela de Duero, Valladolid, Castilla y León)  
**Ayuntamiento gestor:** Tudela de Duero  
**Fecha:** 2026-09-18  
**BOCYL regional (referencia):** 1 aviso

## Resumen

Herrera de Duero **no tiene ayuntamiento propio**; la gestión urbanística corresponde al
**Ayuntamiento de Tudela de Duero**. Las fuentes públicas son la sede electrónica espublico
gestiona, el portal Diputación de Valladolid (`ayuntamientosdevalladolid.es`), el archivo
**PLAI/PLAU JCYL** (municipio 175, INE 47175) y las capas **IDECyL WFS** del municipio matriz.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede electrónica | `https://tudeladeduero.sedelectronica.es` | espublico gestiona | Tablón, trámites, transparencia |
| Tablón de anuncios | `https://tudeladeduero.sedelectronica.es/board` | HTML tabla Wicket | Edictos recientes |
| Catálogo trámites | `https://tudeladeduero.sedelectronica.es/dossier` | HTML Wicket | ~38 trámites urbanismo/licencias |
| Web municipal (Dip.) | `https://tudeladeduero.ayuntamientosdevalladolid.es` | Liferay | Urbanismo, PGOU 2021, normativa |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (municipio 175, prov. 47) | HTML tabla | 11 instrumentos urbanísticos |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/ows` | GeoJSON WFS | 32 sectores PGOU Tudela de Duero |
| Visor SIUCyL | `https://idecyl.jcyl.es/siur/` | Visor web | Cartografía planeamiento CYL |

## Proyectos en Herrera de Duero (PLAI)

Instrumentos con mención explícita a la pedanía:

- **PP RIBERA BLANCA EN HERRERA DE DUERO** (CTU 10/06, 2007)
- **CONVENIO URBANÍSTICO** sector SUD Nº 17 **"EL PINAR" EN HERRERA DE DUERO** (2010)
- **PLAN PARCIAL SECTOR 17 "EL PINAR"** (CTU 82/05, 2006)

El resto de instrumentos PLAI/WFS pertenecen al término municipal de Tudela de Duero (incluye
Herrera y el núcleo principal).

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En la muestra actual predominan subvenciones y empleo;
los anuncios de urbanismo aparecen esporádicamente.

## Licencias

No hay visor georreferenciado municipal de concesiones (sin paridad Madrid DROUS).

- Tablón publica edictos de licencia cuando existen.
- Catálogo sede (`/dossier`) aporta páginas informativas de trámites (licencia, DR, certificados).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 32 polígonos (sectores PGOU Tudela de Duero, p. ej. Sector U-17 "El Pinar")
  - WFS `urbanismo:plau_cyl_planes_parciales` — planes parciales con geometría
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — ámbitos de instrumentos
  - Filtro: `n_mun = 'Tudela de Duero'`, `outputFormat=application/json`, `srsName=EPSG:4326`
- **Estrategia:** ingestar capas WFS del municipio matriz con `geom_geojson`; enriquecer filas
  PLAI/tablón por coincidencia de nombre de sector (`EL PINAR`, `RIBERA BLANCA`, etc.)
- **Limitaciones:**
  - Herrera de Duero no es municipio INE independiente; geometría y planeamiento se consultan
    bajo Tudela de Duero (c_mun 47175)
  - No hay geometría por expediente individual de licencia
  - Web Diputación (`ayuntamientosdevalladolid.es`) puede ser lenta o inaccesible desde CI;
    la sede espublico es la fuente principal operativa
  - PLAI no expone coordenadas; solo PDF/BOCYL

## Notas técnicas

- Código PLAI/PLAU: **175** (provincia 47, INE 47175 Tudela de Duero)
- Sede requiere `CookieJar` + `insecure_ssl: true` para `/dossier`
- PGOU Tudela de Duero aprobado definitivamente nov 2021 (BOCYL 242/2021)
