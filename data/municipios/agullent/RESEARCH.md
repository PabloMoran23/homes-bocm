# Agullent — investigación portal ayuntamiento

**Municipio:** Agullent (Valencia, Comunitat Valenciana)  
**Slug:** `agullent`  
**Boletín:** DOGV (`dogv`, 4 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.agullent.es | Operativa — Drupal 10 portalesmunicipales.es |
| Urbanismo (transparencia) | https://www.agullent.es/es/transparencia/urbanismo | Operativa — PDFs planeamiento consolidado + formularios |
| PUAM | https://www.agullent.es/es/transparencia/plan-urbano-actuacion-municipal | Operativa — anuncios y certificados PUAM |
| Anuncios / bandos | https://www.agullent.es/es/listado/anuncis-bans-i-edictes | Operativa — avisos urbanísticos recientes |
| Sede electrónica | https://agullent.sedelectronica.es | Operativa — espublico gestiona (SSL caducado; `insecure_ssl`) |
| Tablón de anuncios | https://agullent.sedelectronica.es/board/ | Operativa — tabla HTML preview-document |
| Catálogo trámites | https://agullent.sedelectronica.es/dossier | Trámites licencias (sin histórico público) |
| Consulta expedientes | https://agullent.sedelectronica.es/expedientes | Requiere autenticación |

### Avisos urbanísticos recientes (web)

- PFV Agullent I — información pública planta solar fotovoltaica
- PSF Agullent Buenos Aires / Catalí — centrales fotovoltaicas
- Modificación licencia ambiental empresa textil
- Ampliaciones PUAM (certificados y anuncios BOP)

## Cómo se listan expedientes

- **Planeamiento vigente:** shapefile descargable en urbanismo (`SHAPE AGULLENT.zip`) con 149 polígonos y campo `expediente` (16 códigos únicos).
- **Información pública reciente:** páginas `/es/aviso/...` y PDFs en `/sites/www.agullent.es/files/`.
- **Tablón sede:** espublico gestiona, primera página (~10 filas); mayoría no urbanística en el momento del scrape.
- **No hay** visor ArcGIS ni listado HTML de expedientes urbanísticos en curso fuera del tablón.

## Licencias de obra

- Trámites descritos en urbanismo (obra mayor/menor, actividades) con formularios PDF en la web.
- Sin dataset histórico de concesiones con coordenadas.
- Edictos de licencias (ej. modificación licencia ambiental textil) en avisos web.
- Adapter incluye páginas informativas de trámites + tablón sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Shapefile municipal: `https://www.agullent.es/sites/www.agullent.es/files/SHAPE%20AGULLENT.zip`
  - Capa `AGULLENT.shp` — CRS ETRS89 UTM 30N (`EPSG:25830`), campos: `expediente`, `denominaci`, `clas_suelo`, `zon_suelo`
  - 149 features / 16 expedientes de planeamiento (polígonos de zonificación y ámbitos)
- **Estrategia:** descarga ZIP en adapter, lectura con pyshp + reproyección a WGS84 (pyproj). Match por código `expediente` en filas de proyectos.
- **Limitaciones:**
  - Geometría solo para expedientes de planeamiento en el shapefile (no licencias de obra ni fotovoltaicas recientes).
  - Sin visor ArcGIS/WFS público enlazado a expediente individual.
  - Tablón sede sin geometría; anuncios IP fotovoltaica sin polígono en portal.
  - Sede con certificado SSL inválido (`insecure_ssl: true`).

## Limitaciones generales

- Tablón paginado Wicket (solo primera página).
- Consulta expedientes requiere login.
- Web y sede en catalán/valenciano y español.
- Provincia en `queue.yaml` incorrecta (`Agullent`); manifest usa `Valencia`.

## Adapter implementado

- `municipio.adapters.agullent:AgullentAyuntamientoAdapter`
- Fuentes: shapefile planeamiento + avisos/PDFs web + tablón sede + trámites informativos.
