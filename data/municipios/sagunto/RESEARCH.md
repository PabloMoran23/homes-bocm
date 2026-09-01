# Sagunto — investigación portal ayuntamiento

**Municipio:** Sagunto (`sagunto`)  
**Provincia:** Valencia  
**Comunidad Autónoma:** Comunitat Valenciana  
**INE:** 46220  
**Boletín:** DOGV (`dogv`)

> Nota: `sagunt` y `sagunto` son el mismo municipio (castellano/valenciano). Esta entrada usa slug `sagunto` según cola BOCM.

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://aytosagunto.es |
| Urbanismo | https://aytosagunto.es/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/ |
| Planes y convenios | https://aytosagunto.es/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/ |
| PGOU | https://aytosagunto.es/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/planes-ordenacion-y-convenios-urbanisticos/pgou/ |
| Sede sedipualba | https://sagunt.sedipualba.es |
| Tablón de anuncios | https://sagunt.sedipualba.es/tablondeanuncios/ |
| Tablón RSS | https://sagunt.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites urbanismo | https://sagunt.sedipualba.es/catalogoservicios.aspx?area=1260&ambito=1 |
| Transparencia sede | https://sagunt.sedipualba.es/transparencia/ |
| Observatorio Agenda Urbana (ArcGIS Hub) | https://observatorio-de-la-agenda-urbana-de-sagunto-2-aytosagunto.hub.arcgis.com/ |

## CMS y formato de datos

- **Web corporativa:** Umbraco CMS en Azure (`app-aytosaguntopro-webs-webumbraco.azurewebsites.net`). Páginas de urbanismo bajo `/es/ayuntamiento/areas-y-servicios/urbanismo-y-vivienda/` con ~27 expedientes/planes publicados (modificaciones PGOU, PRI, PECHAS, PAI, ordenanzas).
- **Sede electrónica:** Plataforma **sedipualba** (ASP.NET). Tablón de anuncios con RSS XML (`tablon_rss.aspx`). Catálogo de trámites por área; área «Disciplina y Urbanismo» (id=1260) con trámites de compatibilidad urbanística y licencias.
- **Licencias:** No hay dataset público de concesiones. Solo páginas informativas de trámites (certificado compatibilidad urbanística, vivienda turística) y edictos del tablón si mencionan licencias/obras.
- **Proyectos/expedientes:** Páginas Umbraco de planeamiento + sectores ICV WFS + anuncios tablón con keywords urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento` — filtro client-side `cod_ine_mun=46220` (~76 sectores SU/SUZ con polígonos GML en EPSG:4326).
  - ArcGIS Hub «Observatorio Agenda Urbana» — informativo, sin capa enlazable a expedientes concretos.
- **Estrategia:** Descarga paginada WFS (STARTINDEX 0..8000, count=200), filtra por INE 46220, extrae `gml:posList` → GeoJSON Polygon. Matching por tokens sector/UE/PP en título de expediente web o tablón.
- **Limitaciones:** WFS no admite CQL_FILTER efectivo (devuelve toda la CV); requiere paginar y filtrar localmente. Licencias del tablón sin georreferencia. Páginas Umbraco son PDFs/texto sin coords embebidas. ArcGIS Hub no aporta geometría por expediente.

## Limitaciones generales

- Sin visor urbanístico interactivo con enlace expediente→polígono.
- Tablón RSS con muchos anuncios no urbanísticos (subvenciones, plenos, PEIS).
- Sede STA legacy (`sede.sagunto.es`) redirige a sedipualba; no usada.
- Provincia en claim CSV: «Sagunto» (nombre municipio, no «Valencia»).
