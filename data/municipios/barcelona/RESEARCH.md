# Barcelona — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `barcelona` |
| Web | https://www.barcelona.cat / https://ajuntament.barcelona.cat |
| Sede | https://seuelectronica.ajuntament.barcelona.cat |
| PIU | https://ajuntament.barcelona.cat/informaciourbanistica/cerca/es/ |

El Ayuntamiento publica planeamiento, gestión urbanística y calificaciones en el **Portal d'Informació Urbanística (PIU)**, aplicación Angular con API REST bajo `cerca/service/`.

## Fuentes y semillas

| Uso | URL |
|-----|-----|
| Buscador urbanístico | `.../cerca/es/` |
| Config API (`webconfig.js.ashx`) | `.../informaciourbanistica/webconfig.js.ashx?lang=es` |
| Últimas aprobaciones iniciales | `.../cerca/service/DarreresAprovacionsInicials?format=json` |
| Búsqueda unificada | `.../cerca/service/ServeiUnificatRecerca/{texto}?format=json` |
| Geometría ámbito | `.../cerca/service/GeometriaObjecteUrbanistic/{clau1}/{clau2}/{clau3}/{tipus}?format=json` |
| Planol / mapas | https://geoportal.barcelona.cat/planolbcn/ca/ |
| Área urbanismo | https://ajuntament.barcelona.cat/urbanisme-accio-climatica-mobilitat-pla-barris-serveis-urbans/ |

## Listado de expedientes / planeamiento

- **Formato:** JSON (`format=json`) y XML en los mismos endpoints `.ashx`.
- **Búsqueda `pla`:** devuelve bloques `ap` (plans_ordenacio, plans_usos, …), `ag` (gestión), `pu` (proyectos urbanización), `sp` (sectores pendientes), etc. Miles de ámbitos.
- **Metadatos recientes:** `DarreresAprovacionsInicials` aporta `expedient`, fechas BOPB y aprobación inicial para instrumentos en exposición pública.
- **Ficha detalle:** rutas cliente `#/fitxa/{claus}/{tipus}/` (planeamiento `ap`, gestión `ag`, etc.).

## Licencias de obra

- No hay tablón histórico masivo equivalente a sedes `espublico` de municipios pequeños.
- El PIU expone **LlicenciesObres** al consultar una parcela (`InfoCadastre` + expediente); es información vinculada a finca, no listado descargable.
- Trámites: sede electrónica y páginas de información urbanística del área de Ecología Urbana.

## Geometría / visor

- **geometry_status:** `available` (parcial en volumen: no todos los tipos devuelven polígono)
- **Fuentes:**
  - `GeometriaObjecteUrbanistic` — polígonos en **EPSG:25831** (ETRS89 UTM 31N); el adapter reproyecta a WGS84.
  - MapServer interno `mapserv.ashx?ccapa=...` (capas temáticas del plano; requiere contexto de capa/zoom).
  - GeoBCN: `https://w33.bcn.cat/GeoBcn/serveis` (vías, territorio; apoyo al buscador por dirección).
- **Estrategia:** tras listar ámbitos vía `ServeiUnificatRecerca`, consultar geometría con `tipus` acorde (`ap`, `ag`, `pu`, `sp`); límite configurable (`geometry_limit`) por coste de API.
- **Limitaciones:**
  - Instrumentos `pa` con claves `--` a menudo no devuelven geometría; sí `ap`/`ag`/`pu`/`sp`.
  - Coordenadas crudas del servicio no son WGS84 — obligatorio transformar.
  - Licencias sin geometría pública agregada.

## Adapter

- Módulo: `municipio/adapters/barcelona.py`
- IDs: `barcelona-proy-{sha256[:14]}`, `barcelona-lic-{sha256[:14]}`
- User-Agent: `poc-bocm-barcelona/1.0`

## Revisión previa al merge (2026-10-21)

Las páginas informativas se conservan como fuentes en esta investigación, pero
no se exportan como licencias. Sin listado público de concesiones, el adapter
devuelve cero licencias y mantiene la cobertura parcial explícita. La cola
se marca como terminada exclusivamente en el post-merge.
