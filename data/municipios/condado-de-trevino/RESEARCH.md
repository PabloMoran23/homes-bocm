# Condado de Treviño — investigación portal ayuntamiento

Municipio enclave de la provincia de Burgos (Castilla y León), rodeado por Álava. INE `09109`.

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (Drupal) | https://www.condadodetrevino.es/inicio |
| Sede electrónica (espublico) | https://condadodetrevino.sedelectronica.es/ |
| Tablón de anuncios | https://condadodetrevino.sedelectronica.es/board |
| Transparencia — urbanismo (7.1 planeamiento) | https://condadodetrevino.sedelectronica.es/transparency/6a9a765c-bc20-4432-a8ac-e03789d26539/ |
| NUM en sede (PDF) | https://condadodetrevino.sedelectronica.es/preview-document/1c2cd4d2-f96a-45fe-99d0-c48d75105853 |
| Trámites OBRAS | https://condadodetrevino.sedelectronica.es/citizen-service/b6a90317-cfae-4509-83c3-6ac86af25715 |
| PLAI JCYL (prov=09, mun=109) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=109 |
| IDECyL WFS urbanismo | https://idecyl.jcyl.es/geoserver/urbanismo/ows |

## Expedientes / planeamiento

- **CMS web:** Drupal (Volt ADC). Menú enlaza sede y transparencia; no hay listado propio de expedientes urbanísticos en la web.
- **Sede espublico:** tablón Wicket con filas `preview-document/{uuid}` (documento, expediente, procedimiento, categoría, fecha). Actualmente pocos anuncios de urbanismo; mayoría administrativa (calendario fiscal, incendios, etc.).
- **Transparencia:** sección 7.1 con enlace al PDF de NORMAS URBANÍSTICAS MUNICIPALES.
- **PLAI JCYL:** ~15 documentos históricos (planes parciales PP en núcleos FRANCO, ARRIETA, AGUILLO, etc.) + instrumento NUM vigente (aprobación feb 2022, BOCYL mar 2022). HTML tabular con `cDocId`.
- **Consulta expedientes** (`/expedientes`) requiere identificación; no scrapeable sin credenciales.

## Licencias de obra

- No hay dataset ni listado público de concesiones de licencia en tablón.
- Trámite **OBRAS** en sede (`citizen-service/b6a90317-…`) y catálogo `/dossier` — páginas informativas de solicitud.
- El adapter devuelve filas informativas de trámite (patrón Pozuelo/Monfarracinos).

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - IDECyL GeoServer WFS `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Condado de Treviño'` (c_mun=09109): 1 polígono NUM (~260 km²).
  - WFS `urbanismo:plau_cyl_sectores` — 5 sectores con geometría MultiPolygon.
  - WFS `urbanismo:plau_cyl_planes_parciales` — 0 features para este municipio.
  - PLAI mapa integrado en JCYL (no visor municipal independiente).
- **Estrategia:** query WFS con `outputFormat=application/json`, `srsName=EPSG:4326`; enriquecer proyectos PLAI/tablón por coincidencia de tokens en título (sector FR-1, VA-2, etc.).
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin georreferencia; tablón sin coords; `/expedientes` con login.

## Limitaciones generales

- Enclave administrativo: datos en PLAI bajo provincia Burgos (09) aunque geográficamente en País Vasco.
- Tablón con poca actividad urbanística reciente.
- Sin licencias concedidas publicadas en abierto.
