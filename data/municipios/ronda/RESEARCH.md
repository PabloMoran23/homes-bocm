# Ronda — investigación portal ayuntamiento

**Municipio:** Ronda (Málaga, Andalucía)  
**Slug:** `ronda`  
**Boletín:** BOJA (`boja`, 19 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayuntamientoronda.es | WordPress; noticias urbanismo |
| Sede electrónica | https://ronda.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://ronda.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket |
| Transparencia — planeamiento | https://ronda.sedelectronica.es/transparency/0a2ade64-34c4-4f6c-927a-bb54d949eeee/ | Carpetas PGOU, planes especiales, estudios de detalle |
| Actos urbanísticos (info) | https://ronda.sedelectronica.es/citizen-service/57afef79-c147-453e-bc9c-61c4ca688ba3 | Trámites informativos licencias/DR |
| Consulta expedientes | https://ronda.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Visor urbanismo UNOData | https://visor.urbanismoronda.es/ → https://geoportal.unodata.urbanismoronda.es/ | Leaflet + API REST pública |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Griñón, Algete.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).

### Ejemplos urbanísticos encontrados (jul 2026)

| Procedimiento | Descripción |
|---------------|-------------|
| Licencias de Actividad | Licencia apertura hostelería C/ Genal nº 6 (ref. catastral 7195118UF0679N0001AQ) |
| Licencias Urbanísticas | Edicto información pública actuación extraordinaria suelo rústico |
| Contrataciones Patrimoniales | Información pública concesión aseos Alameda |
| Disposiciones Normativas | Aprobación inicial ordenanza de vertidos |

## Transparencia — planeamiento urbanístico

- **Sección:** 7.1 PLANEAMIENTO URBANÍSTICO (portal transparencia sede).
- **Formato:** carpetas expandibles Wicket (`gIconLink exp`) con títulos de expedientes/planes.
- **Documentos listados:** PGOU texto refundido, planes especiales (El Fuerte, El Cotillo, conjunto histórico), estudios de detalle, avance PGOM, innovaciones PGOU.
- **Enlaces:** carpetas requieren AJAX Wicket para PDFs individuales; el adapter indexa títulos de carpeta con URL de la sección.

## Licencias de obra

- No hay dataset histórico público de concesiones.
- Licencias y edictos publicados en tablón (`Licencias Urbanísticas`, `Licencias de Actividad`).
- Trámites informativos en sede «Actos urbanísticos» y catálogo `/dossier`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor UNOData: `https://geoportal.unodata.urbanismoronda.es/`
  - API REST: `restapi/index.php?operacion=VisorAbierto&tipo=buscador&subtipo=refcat&token=...&refcat={ref}`
  - Respuesta: `Parcelas[].geometria` — GeoJSON Polygon en WGS84 (coordenadas `[lon, lat]`).
  - Capas WMS/ArcGIS del visor cargadas vía `tipo=cargaInicial` (espacio GeoServer `Ronda`).
- **Estrategia:** extraer referencia catastral del texto del tablón (p. ej. `Ref. catastral: 7195118UF0679N0001AQ`) y consultar API UNOData para polígono parcela.
- **Limitaciones:**
  - Solo parcelas con ref. catastral explícita en el anuncio (no enlazable por código de expediente).
  - Documentos de planeamiento en transparencia no incluyen geometría embebida.
  - Planes generales/ámbitos no consultables por expediente del tablón.

## Limitaciones generales

- Tablón paginado con AJAX Wicket (primera página en adapter).
- Transparencia: subcarpetas requieren sesión Wicket para PDFs individuales.
- Consulta de expedientes requiere login.
- Web corporativa WordPress no usada como fuente principal (sede más estable).

## Adapter implementado

- `municipio.adapters.ronda:RondaAyuntamientoAdapter`
- Fuentes: tablón sede + transparencia planeamiento + geometría UNOData por ref. catastral.
- IDs: `ronda-lic-*` / `ronda-proy-*` (sha256[:14]).
