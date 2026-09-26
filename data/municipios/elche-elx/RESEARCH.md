# Elche/Elx — investigación portal ayuntamiento

Municipio: Elche/Elx (`elche-elx`), provincia Alicante, Comunitat Valenciana. Boletín: DOGV (`dogv`). INE: 03065.

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.elche.es/ |
| Urbanismo | https://www.elche.es/urbanismo/ |
| Tablón anuncios (web) | https://www.elche.es/urbanismo/tablon-anuncios/ |
| Documentación en tramitación | https://www.elche.es/urbanismo/documentacion-urbanistica-en-tramitacion/ |
| Planeamiento, gestión y urbanización | https://www.elche.es/urbanismo/planeamiento-gestion-y-urbanizacion/ |
| Modificaciones puntuales PG | https://www.elche.es/urbanismo/planeamiento-gestion-y-urbanizacion/modificaciones-puntuales-pg/ |
| Planes parciales | https://www.elche.es/urbanismo-2/planeamiento-y-gestion-2/planes-parciales |
| Planes especiales | https://www.elche.es/urbanismo-2/planeamiento-y-gestion-2/planes-especiales |
| Estudios de detalle | https://www.elche.es/urbanismo-2/planeamiento-y-gestion/estudios-de-detalle |
| Sede electrónica STA | https://sede.elche.es/sta/ |
| Tablón sede | https://sede.elche.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES |
| Catálogo trámites | https://sede.elche.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03065%20ELCHE/ |

## Listado de expedientes / proyectos

- **Web WordPress (citygov):** secciones de urbanismo con PDFs en `/wp-content/uploads/` (edictos IP, certificados de aprobación, modificaciones puntuales, planes parciales). Listados estáticos en HTML (~50+ PDFs urbanísticos).
- **Tablón web:** página `urbanismo/tablon-anuncios/` con PDFs de edictos, certificados pleno, resoluciones (~21 documentos).
- **Sede STA tablón:** `PTS2_TABLON` con `KEY=all` embebe `var dataset_PTS2_TABLON = [...]` (mismo patrón TAO que Dénia). Puede tener timeout en CI (>60s); el adapter reintenta y usa web como fallback.
- **No hay** visor municipal ArcGIS/gvsig propio enlazable por expediente. El buscador de urbanismo es página informativa sin API.

## Licencias

- **Tablón web/sede:** edictos de información pública y resoluciones; pocas concesiones individuales con dirección.
- **Catálogo sede:** trámites de licencias de obra, DR, compatibilidad urbanística (páginas informativas).
- **No hay** dataset público de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: sectores SU/SUZ y unidades de ejecución
  - Filtro cliente: `cod_ine_mun=03065` (Elche/Elx)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`)
  - Paginación: `STARTINDEX` + `count=200` (CQL_FILTER no fiable)
  - **123 polígonos** para Elche en ICV
- **Estrategia:** descargar WFS paginado, filtrar INE 03065, convertir `gml:posList` → GeoJSON Polygon; enriquecer proyectos por token de sector (`UE-*`, `MP-*`, `BS-*`) en título/PDF.
- **Limitaciones:** sin visor municipal propio; geometría ICV cubre sectores planificados pero no expedientes individuales del tablón ni licencias. Matching por nombre de sector, no por código de expediente.

## Limitaciones

- Sede STA puede timeout en entornos CI (BitNinja/WAF); web WordPress es fuente principal.
- Tablón mezcla subvenciones/personal; filtro regex urbanismo.
- Sin listado público de licencias concedidas con dirección/coords.
- PDFs sin georreferencia directa.

## Adapter

- `municipio.adapters.elche_elx:ElcheElxAyuntamientoAdapter`
- Fuentes: PDFs web urbanismo + tablón web + tablón/catálogo sede (si accesible) + ICV WFS
