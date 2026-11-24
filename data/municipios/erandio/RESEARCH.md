# Erandio — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `erandio` |
| CCAA | Euskadi (Bizkaia) |
| INE | 48027 |

El ayuntamiento publica trámites de urbanismo en **Tramitegunea** (`tramitegunea.erandio.eus`). La web corporativa histórica (`www.erandio.eus`) no respondió desde el entorno del agente; el portal activo accesible es **app.erandio.eus** (WordPress/Divi) con información del área de Territorio.

No hay tablón municipal scrapeable con PDFs de licencias/concesiones enlazado desde fuentes públicas encontradas. Las licencias se documentan como **fichas de trámite** (sin histórico de concesiones).

## Fuentes

### Trámites / licencias

- **Manual de trámites:** https://tramitegunea.erandio.eus/?lang=es  
  Listado HTML por familias; fichas `/front/procedure/{id}?lang=es` (obra mayor, comunicaciones previas, actividad clasificada, etc.).
- **Información urbanística:** https://tramitegunea.erandio.eus/front/procedure/174?lang=es  
- **Territorio (contexto):** https://app.erandio.eus/territo/

### Planeamiento / expedientes

- **Registro PUR Diputación Foral de Bizkaia:**  
  https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador  
  Filtro municipio **ERANDIO** (`select-municipios=902`). POST Liferay; tarjetas HTML con año, título e `idInstrumento`.
- No se localizó sede STA ni tablón de anuncios municipal con expedientes urbanísticos indexables (SharePoint/espublico).

## Formato de datos

| Fuente | Formato | Campos útiles |
|--------|---------|---------------|
| Tramitegunea | HTML estático | título trámite, URL ficha |
| PUR Bizkaia | HTML POST | año, título instrumento, código `(…)`, enlace detalle |
| ArcGIS Diputación | REST GeoJSON | `NombreAmbito`, polígonos clasificación/usos |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - MapServer: `https://geo.bizkaia.eus/arcgisserverinspire/rest/services/LurraldeAntolamendua_PlanificacionTerritorial/Plangintza_Planeamiento/MapServer`
  - Capas clasificación suelo municipio `ERANDIO`: ids 1–3 (`Municipio='ERANDIO'`).
  - Capas ámbitos con `NombreAmbito`: ids 41, 42, 23 — query `UPPER(NombreAmbito) LIKE '%TOKEN%'` cruzando tokens del título PUR.
- **Estrategia:** tras ingest PUR, enriquecer con query ArcGIS por tokens del título; añadir 3 filas PGOU de clasificación con polígono municipal.
- **Limitaciones:** sin visor municipal por expediente; PUR no trae geometría; matching por nombre es parcial (p. ej. PERI Astrabudua); licencias solo trámites sin coords.

## Limitaciones generales

- `www.erandio.eus` inaccesible (timeout) en pruebas del agente.
- Sin dataset público de licencias concedidas.
- Geometría por instrumento depende de coincidencia textual en `NombreAmbito` (Diputación).

## Referencias implementación

- Patrón PUR: `municipio/adapters/santurtzi.py` (Bizkaia id 82 → Erandio **902**).
- Patrón ArcGIS clasificación: `municipio/adapters/portugalete.py`.
- Trámites informativos licencias: `municipio/adapters/errenteria.py`, `pozuelo.py`.
