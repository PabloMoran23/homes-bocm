# Cabrerizos — investigación portal ayuntamiento

**Municipio:** Cabrerizos (Salamanca, Castilla y León)  
**Fecha:** 2026-08-26  
**BOCYL regional (referencia):** 2 avisos

## Resumen

Cabrerizos publica planeamiento en la web corporativa WordPress Divi (`ayto-cabrerizos.com/urbanismo/`)
con decenas de PDFs de NNSS, sectores y modificaciones. La sede electrónica usa **eAdmin Add4u**
(`sedeelectronica.ayto-cabrerizos.com`) pero el backend de gestión documental devuelve HTTP 500
(`Connection refused` al servicio interno). El planeamiento histórico está en **PLAI JCYL**
(municipio 067, provincia 37) y la cartografía sectorial en **IDECyL WFS** (c_mun 37067).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://ayto-cabrerizos.com` | WordPress Divi | Urbanismo, formularios trámites |
| Urbanismo | `https://ayto-cabrerizos.com/urbanismo/` | HTML + PDFs | NNSS, sectores U.Ur-*, PERI, estudios detalle |
| Formularios | `https://ayto-cabrerizos.com/formularios-tramites/` | HTML + PDFs | Impresos URB-* licencias y DR |
| Sede eAdmin | `https://sedeelectronica.ayto-cabrerizos.com/eAdmin/` | Struts JSP | Trámites urbanismo (tablón 500) |
| Sede legacy | `https://cabrerizos.sedelectronica.es` | HTML | Inactiva |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (mun. 067, prov. 37) | HTML tabla | ~15 instrumentos aprobados |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | 30 sectores + 1 NNSS |

## Urbanismo web (`/urbanismo/`)

Página con pestañas Divi (planeamiento vigente, licencias, consultas). Enlaces directos a PDFs en
`/wp-content/uploads/`:

- NNSS completas (memoria, planos, BOCYL 1996)
- Sectores U.Ur-8, U.Ur-12, U.Ur-19, I.UR-2, UR.CON-8, PERI ER-2/ER-4
- Modificaciones NNSS (La Flecha, U.Ur-8, UR.CON-8)
- Estudios de detalle (ER-2, Juan López U.Ur-5)
- BOCYL recientes (U.Ur-19.3, 2026)

REST API WP disponible (`/wp-json/wp/v2/pages/628` urbanismo).

## Sede eAdmin

Catálogo de trámites urbanísticos accesible vía `Registrar.do?action=listadoEntradas` (lista tipos)
pero tablón (`Tablon.do?action=verAnuncios`) y registro devuelven **HTTP 500** por fallo del servicio
Axis `GestDocRE` (conexión rehusada). No hay listado público de concesiones en el momento de la investigación.

Trámites identificados (solo informativos):

- 03 URBANISMO. 1 Licencias de Obras (4 subtipos)
- 03 URBANISMO. 2 Declaraciones Responsables de Obras (3 subtipos)
- 03 URBANISMO. Certificaciones Urbanísticas

Impresos PDF equivalentes en `/formularios-tramites/` (URB-LICENCIA-*, URB-DECLARACION-RESPONSABLE-*).

## PLAI JCYL

Código municipio PLAI: **067** (provincia 37). Documentos incluyen:

- PP LAS DUNAS, PP SECTOR UR-4, PP UR-2 LA RECOVA
- PLAN PARCIAL U.Ur-8 TESO DE LA CRUZ
- PLAN PARCIAL U.Ur-12 CRUZ DE CHICOLA
- PERI ER-2, PERI ER-4
- Modificación PP I-UR INDUSTRIAL
- Estudios de detalle ER-2, U.Ur-5 Juan López
- Proyectos de urbanización U.Ur-5, U.Ur-12

## Licencias

No hay visor georreferenciado municipal de concesiones de obra.

- Sede eAdmin tablón inaccesible (500)
- Formularios WP publican impresos de solicitud (licencia construcción, ampliación, segregación, DR obras, etc.)
- Trámites eAdmin informativos enlazados desde formularios

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 30 polígonos (U.Ur-*, UR-*, I.UR-2, UR.CON-*, etc.)
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NNSS (c_plan 37067-PU-19960612-292935)
  - WFS `urbanismo:plau_cyl_planes_parciales` — planes parciales Cabrerizos
  - Filtro: `n_mun = 'Cabrerizos'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Visor SIUCyL: `https://idecyl.jcyl.es/siur/` (sin enlace directo a expediente)
- **Estrategia:** ingestar capas WFS como proyectos con `geom_geojson`; enriquecer filas PLAI/WP
  por coincidencia de código sector en título (U.Ur-8, UR-2, I.UR-2, etc.)
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia
  - Sede eAdmin tablón caído; sin concesiones publicadas scrapeables
  - PLAI no expone coordenadas; solo PDF/BOCYL
  - PDFs web sin georreferenciación embebida

## Limitaciones generales

- Sede eAdmin backend documental inaccesible (500 persistente)
- `www.cabrerizos.es` no resuelve; dominio activo es `ayto-cabrerizos.com`
- Sede legacy `cabrerizos.sedelectronica.es` inactiva
