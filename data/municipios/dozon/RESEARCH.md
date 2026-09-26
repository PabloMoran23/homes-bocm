# Dozón — investigación portal ayuntamiento

Municipio: **Dozón** (`dozon`) — Galicia, provincia Pontevedra (comarca O Deza).  
INE: **36016**. Boletín: **DOG** (`dog`, 1 entrada BOCM legacy).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.dozon.gal/web/ | WordPress (turismo, parroquias, sede). Sin sección urbanismo/planeamiento. |
| Sede electrónica | https://dozon.sedelectronica.gal/ | espublico gestiona (Wicket/YUI). |
| Tablón de anuncios | https://dozon.sedelectronica.gal/board | Tabla HTML vacía (`emptyTable`). |
| Catálogo trámites | https://dozon.sedelectronica.gal/dossier | Trámites urbanísticos informativos. |
| Transparencia | https://dozon.sedelectronica.gal/transparency | Sin documentos urbanismo enlazados. |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Plan Básico Autonómico (sin PGOM). |
| Visor PBA Xunta | https://mapas.xunta.gal/visores/pba/ | Normas subsidiarias provinciales / PBA. |
| DOG Plan básico municipal | https://www.xunta.gal/dog/Publicados/2024/20240131/AnuncioG0691-220124-0003_es.html | IP Plan básico municipal (2024-01-23). |
| Participación pública Xunta | https://cmatv.xunta.gal/seccion-tema/c/CMAOT_Territorio_e_urbanismo_Planeamento_urbanistico | Portal Consellería planeamiento. |

## Expedientes / proyectos

- **Ayuntamiento:** no publica expedientes urbanísticos ni visor propio. El tablón de anuncios está vacío.
- **Xunta de Galicia:** Dozón tiene **Plan Básico Autonómico** (sin planeamiento general adaptado a la LSG). En 2024 se sometió a información pública el **Plan básico municipal** (tramitación autonómica, <5.000 hab.).
- **SIOTUGA:** fila INE 36016 sin enlace WMS ni inventario municipal detallado (a diferencia de concellos con PGOM).
- **Listado:** registros fijos DOG/SIOTUGA + crawl del catálogo de trámites (informativo).

## Licencias

- No hay listado público de licencias concedidas.
- La sede expone trámites de licencia/autorización urbanística, declaración responsable/comunicación urbanística y licencias de actividad (páginas informativas del catálogo espublico).
- Estrategia adapter: páginas de trámite como filas informativas (`min_rows: 0` en licencias).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SIOTUGA urb: Dozón (36016) sin celda WMS ni inventario enlazable.
  - mapas.xunta.gal/visores/pba/: visor autonómico PBA, sin query por expediente municipal.
  - Sede / web: sin ArcGIS, WFS ni GeoJSON.
- **Estrategia:** sin polígonos por proyecto; el orquestador aplicará centroide municipio + jitter (`centroid` en manifest).
- **Limitaciones:** municipio pequeño sin PGOM; planeamiento en manos de la Xunta; tablón vacío; solo PDFs normativos autonómicos.

## Limitaciones técnicas

- Sede espublico requiere cookie jar (redirects `info` → `info.0`).
- Tablón sin filas scrapeables.
- Primera carga de sede puede tardar ~20 s (timeout generoso en adapter).
- Sin `insecure_ssl` necesario (certificados válidos).
