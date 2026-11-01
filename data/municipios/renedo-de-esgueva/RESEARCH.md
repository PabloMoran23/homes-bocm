# Renedo de Esgueva — investigación portal ayuntamiento

**Municipio:** Renedo de Esgueva (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-10-14  
**BOCYL (referencia):** 1 aviso  
**INE:** 47133

## Resumen

Renedo de Esgueva publica información institucional en **WordPress** (`ayto.renedodeesgueva.es`) y la administración digital en **sede electrónica espublico gestiona** (`renedodeesgueva.sedelectronica.es`). El planeamiento urbanístico aprobado está en **PlanPublica** (Junta de CYL, código municipio **133** en provincia **47**). No hay listado público de licencias de obra concedidas con coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://ayto.renedodeesgueva.es/ | WordPress; sección Urbanismo y Vivienda informativa |
| Urbanismo (web) | https://ayto.renedodeesgueva.es/departamento/urbanismo-y-vivienda/ | Sin listado de expedientes ni PDFs PGOU indexados |
| Sede electrónica | https://renedodeesgueva.sedelectronica.es/info | Redirige desde `/` |
| Tablón de anuncios | https://renedodeesgueva.sedelectronica.es/board | Tabla Wicket + PDFs `preview-document` |
| Trámites | https://renedodeesgueva.sedelectronica.es/dossier | Catálogo espublico |
| Transparencia | https://renedodeesgueva.sedelectronica.es/transparency | 129 docs en «Urbanismo, Obras Públicas y Medio Ambiente» |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=133 | Archivo planeamiento aprobado (PGOU, PP, PE, ED…) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=133 | Información pública |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=47133 | Visor regional de instrumentos |

**Contacto:** Pl. del Guindo, 1, 47170 Renedo de Esgueva · Tel. 983 508 027 · administracion@renedodeesgueva.es

## 2. Urbanismo / expedientes

### PlanPublica (PLAU)

Tabla HTML con filas `Libro / Tipo / fechas / Título`. Incluye PGOU (2015), planes parciales históricos, estudios de detalle (p. ej. sector 19), plan especial de comunicaciones, etc. Enlaces PDF vía `openDocumento.do?cDocId=…`.

### Tablón de anuncios

Listado con columnas documento, expediente, procedimiento, categoría, descripción, fecha. En la muestra (oct 2026) predominan avisos no urbanísticos (censo electoral, contratación, tributos). Sin licencias de obra explícitas.

### Licencias

No hay dataset ni tablón dedicado a concesiones georreferenciadas. Trámites de licencia en catálogo espublico; el adapter recoge anuncios futuros en tablón si aparecen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Renedo de Esgueva'`
  - SiUR visor regional INE `47133`
- **Estrategia:** descarga WFS por municipio (1 ámbito PGOU + varios sectores); enriquecimiento de proyectos PLAU/tablón por código de sector en título.
- **Limitaciones:** sin visor municipal propio; licencias sin geometría; sede puede requerir `insecure_ssl` según cadena CA del entorno.

## 3. Implementación adapter

Patrón **CYL espublico + PlanPublica + IDECyL WFS** (Narros de Matalayegua / Pesquera de Duero): `urllib`, tablón sede, parseo PLAU/PLAI, enriquecimiento WFS (`geom_geojson`, `geometry_source=portal_wfs`).
