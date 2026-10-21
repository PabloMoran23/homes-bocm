# Zaragoza — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Sede / urbanismo | https://www.zaragoza.es/sede/portal/urbanismo/ |
| Información pública (planeamiento) | https://www.zaragoza.es/sede/portal/urbanismo/planeamiento/informacion-publica |
| Tablón de edictos | https://www.zaragoza.es/sede/servicio/tablon-edicto/ |
| Trámites urbanismo | https://www.zaragoza.es/sede/portal/urbanismo/tramites |
| Visor cartografía planeamiento | https://idezar-sig.zaragoza.es/servicios/visorUrbanismo/ |
| Datos geográficos urbanismo | https://www.zaragoza.es/sede/portal/urbanismo/info-geografica/datos |

## Proyectos / expedientes

- **Instrumentos de planeamiento (histórico y vigente):** capa WFS GeoServer IDEZar `urbanismo:PLA_1_Instrumentos_ambito` (~523 registros) con campos `expediente`, `codigo_ambito`, `nombre_instrumento`, enlaces a PDFs de acuerdos/planos.
- **Información pública activa:** listado estático de PDFs en la página de IP (`/contenidos/urbanismo/informacion-publica/...`).
- **Tablón:** items JSON en `/sede/servicio/tablon-edicto/{id}.json`; extractos del Consejo de Gerencia de Urbanismo complementan novedades recientes.

Formato: JSON REST en sede + GeoJSON vía WFS; HTML en portal IP.

## Licencias de obra

No hay dataset público de concesiones de licencia (como tablón de licencias otorgadas). La sede expone **trámites** (`/sede/servicio/tramite/{id}.json`) filtrados desde el portal de urbanismo (licencia obra mayor, comunicación previa, DR obras menores, etc.). El adapter registra esas fichas informativas (`min_rows: 0` en licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `urbanismo:PLA_1_Ambitos_desarrollo` y `urbanismo:PLA_1_Ambitos_recogido` (polígonos por `codigo_ambito`)
  - Visor web: https://idezar-sig.zaragoza.es/servicios/visorUrbanismo/
  - WMS/WFS capabilities: `https://idezar-sig.zaragoza.es/servicios/geoserver/urbanismo/wfs`
- **Estrategia:** join `PLA_1_Instrumentos_ambito.codigo_ambito` → polígono del ámbito en capas de ámbitos; ~222/523 instrumentos con polígono en prueba local.
- **Limitaciones:** la capa de instrumentos no trae geometría; IP en PDF sin georreferencia; licencias sin ubicación; CRS de salida WFS en GeoJSON usable en EPSG:4326.

## Limitaciones generales

- `tablon-edicto/list.json` devuelve error 400 (no usable para listado masivo).
- Buscador sede requiere login para algunas APIs.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
