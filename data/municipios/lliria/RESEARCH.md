# Llíria — investigación portal ayuntamiento

Municipio: Llíria (`lliria`), provincia Valencia, Comunitat Valenciana. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (Drupal) | https://www.lliria.es/es |
| Sede electrónica STA (TAO) | https://sede.lliria.es/sta/ |
| Tablón anuncios | https://sede.lliria.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES |
| Catálogo trámites | https://sede.lliria.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Urbanismo (web, intermitente) | https://www.lliria.es/es/areas-municipales/urbanismo |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20VALENCIA/46146%20LLIRIA/ |

## Listado de expedientes / proyectos

- **Sede STA tablón:** página `PTS_TABLON` embebe `var dataset_TABLON = [...]` (~123 anuncios, ~10–15 urbanismo/planeamiento). Campos: `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `remitent.description`.
- **Ejemplos tablón:** modificación PGOU nº29, urbanización sector SRE-4 Camí de Mura, PAI sector ST-1, expropiaciones UE-A/UE-B, PPOS Polideportivo El Canó.
- **Web Drupal:** CMS estándar; en CI la home (`www.lliria.es`) suele timeout (>60s). Sin API pública de expedientes detectada.
- **No hay** visor municipal ArcGIS con expedientes enlazables.

## Licencias

- **Tablón:** anuncios de obras/urbanización; no listado de concesiones individuales con dirección.
- **Catálogo sede:** ~60 trámites urbanísticos (licencia urbanística obra, DR, certificado urbanístico, compatibilidad, urbanización, etc.). Páginas informativas sin histórico de concesiones.
- **Sin dataset** de licencias concedidas con coords.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: sectores SU/SUZ (SUNP-1, SUNP-2, SUP-1, SUP-2, SUP-3, unidades UE)
  - Filtro cliente: `cod_ine_mun=46146` (Llíria)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`); GeoJSON no soportado
  - Paginación: `STARTINDEX` + `count=200`
- **Estrategia:** descargar WFS paginado, filtrar INE 46146 (7 polígonos), convertir `gml:posList` → GeoJSON Polygon; enriquecer proyectos del tablón por tokens de sector (SRE-4, ST-1, UE-A, SUNP, SUP, etc.).
- **Limitaciones:** 7 polígonos ICV (sectores planificados), sin geometría para licencias ni expedientes individuales del tablón. `www.lliria.es` inaccesible en CI → adapter prioriza sede + WFS.

## Limitaciones

- Tablón mezcla subvenciones, personal, contratación; filtro regex urbanismo/planeamiento.
- Web Drupal con timeout frecuente desde CI (no bloqueante: sede + ICV suficientes).
- ICV WFS no enlaza código de expediente municipal; matching por nombre de sector/UE.
- Sede legacy `lliria.sedelectronica.es` inactiva (página selector genérica espublico).

## Adapter

- `municipio.adapters.lliria:LliriaAyuntamientoAdapter`
- Fuentes: tablón STA + ICV WFS + catálogo trámites (licencias informativas) + PDFs web (opcional)
