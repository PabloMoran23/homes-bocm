# Burgos — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Portal web | https://www.aytoburgos.es |
| Urbanismo | https://www.aytoburgos.es/urbanismo |
| Tablón anuncios urbanismo (Liferay) | https://www.aytoburgos.es/anuncios-urbanismo |
| Instrumentos planeamiento y gestión | https://www.aytoburgos.es/instrumentos-planeamiento-gestion |
| Sede electrónica (STA / TAO) | https://sede.aytoburgos.es |
| Tablón edictos sede | https://sede.aytoburgos.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON |
| Catálogo trámites | https://sede.aytoburgos.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Visor cartográfico | https://ide.aytoburgos.es/ |

## Proyectos / expedientes urbanísticos

### 1. Instrumentos de planeamiento (Liferay Asset Publisher)

Tabla HTML en `/instrumentos-planeamiento-gestion` con ~46 filas. Campos: código expediente
(`000003/2025 EST-PGOU`), descripción, promotor y enlace a ficha Liferay
(`/asset_publisher/.../content/...`).

### 2. Tablón de anuncios urbanismo (Liferay)

`/anuncios-urbanismo` lista ~45 anuncios paginados (3 páginas). Códigos tipo
`000005/2023 URB-PGOU`, `2/2023 EXC-URB`, `00002/2025 PROV-URB`. Enlaces a fichas
con documentación PDF en `/documents/38509/...`.

### 3. Sede STA — tablón de edictos

Página `PTS2_TABLON` embebe JSON `dataset_PTS2_TABLON` (~112 filas totales).
Filas de **Gerencia Municipal de Urbanismo, Infraestructuras y Vivienda** incluyen
aprobaciones iniciales de estudios de detalle, modificaciones PGOU, etc.
Campos: `descriptionProc`, `remitent.description`, `pubDateIni`, `dboid`.

## Licencias de obra

No hay listado público de licencias concedidas con coordenadas. Fuentes disponibles:

1. **Catálogo STA (`dataset_CATSERV`)**: ~28 trámites con keyword `LICENCIAS`
   (declaración responsable obras, licencia nueva planta, etc.) — páginas informativas.
2. **Tablón STA**: ocasionales anuncios de licencias ambientales o similares; no hay
   tablón sistemático de licencias de obra concedidas.

Estrategia adapter: trámites CATSERV como filas informativas (patrón Parla/Pozuelo).
Si la sede STA no es accesible (connection reset desde CI), fallback a páginas
`/licencias-y-servicios` del portal Liferay.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor de Información Geográfica y Urbanística en
  https://ide.aytoburgos.es/ (enlazado desde `/urbanismo` y `/mapa-web`). Referenciado
  en documentación PGOU como fuente de planimetría y delimitación de sectores.
- **Estrategia:** El visor es una aplicación web propia; no expone MapServer/WFS público
  descubierto. `ide.aytoburgos.es` rechaza conexión TLS desde el entorno del agente
  (connection reset). Sin API REST/ArcGIS/WFS enlazable al código de expediente.
- **Limitaciones:** Solo consulta interactiva en visor; geometría en PDFs/planos sin
  georreferencia automática. El orquestador usará centroide municipal + jitter.

## Limitaciones generales

- Portal Liferay: paginación manual en anuncios (3 páginas).
- Sede STA: certificado TLS válido pero dataset embebido requiere parseo JS.
- Expedientes completos en sede requieren identificación (`EXPEDIENTES_FULL` privado).
- Sin dataset abierto de licencias concedidas.
