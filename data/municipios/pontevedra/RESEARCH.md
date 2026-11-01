# Pontevedra — investigación portal ayuntamiento

Municipio: **Pontevedra** (`pontevedra`) — Galicia, provincia Pontevedra.  
INE: **36038**. Sin boletín regional asociado en cola (`bocm_count: 0`).

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://pontevedra.gal |
| Urbanismo | https://pontevedra.gal/areas/urbanismo-e-territorio/ |
| Planeamento | https://pontevedra.gal/areas/urbanismo-e-territorio/planeamento-urbanistico/ |
| PXOU / modificacións | https://pontevedra.gal/areas/urbanismo-e-territorio/planeamento-urbanistico/pxou-e-modificacions-realizadas/ |
| PXOM (futuro) | https://pontevedra.gal/areas/urbanismo-e-territorio/o-futuro-pxom/ |
| Trámites urbanísticos | https://pontevedra.gal/areas/urbanismo-e-territorio/tramites-urbanisticos/ |
| Sede electrónica | https://sede.pontevedra.gal/ |
| Convenios urbanísticos (sede) | https://sede.pontevedra.gal/public/convenio/convenio-index.xhtml |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36038&lang=es_ES |
| Catafis (SIG) | https://catafis.pontevedra.gal/ |

## Proyectos / planeamiento

- **CMS:** WordPress en `pontevedra.gal` (rutas `/areas/urbanismo-e-territorio/...`). Documentación en HTML y PDFs (`/PXOU/`, `/URBANISMO-docs/`, enlaces BOP provincia).
- **Inventario normativo:** **SIOTUGA** (Xunta) expone ~42 instrumentos de plan xeral (idclase 14) y ~77 de desenvolvemento (idclase 13) para INE 36038. API POST `query_document.php` con `id`, `token` (sesión) e `idclase`.
- **Sede:** aplicación Java/JSF; publicacións y transparencia. No se obtuvo listado de anuncios urbanísticos en tiempo razonable desde el entorno cloud (>60s timeout).
- **Participación:** procesos en `pontevedra.gal/participa/` (ordenanzas); no sustituyen inventario de expedientes.

## Licencias de obra

- No hay tablón público de **licencias concedidas** con dirección/fecha.
- Página de trámites enlaza documentación informativa (2017):
  - https://www.pontevedra.gal/URBANISMO-docs/2017-06-26_Licenzas.pdf
  - https://www.pontevedra.gal/URBANISMO-docs/2017-06-26_Comunicacions-previas.pdf
- Tramitación vía sede (formularios / cita previa OTLL); sin dataset abierto de concesiones.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** **Catafis** — portal SIG municipal (Leaflet, backend `geotxt.pontevedra.eu` para textos CMS). Capas de planeamento y catastro consultables en mapa, pero **sin campo de enlace** a códigos de expediente del inventario SIOTUGA ni listados de licencias.
- **Estrategia:** el adapter documenta Catafis como semilla; el orquestador usará centroide municipal + jitter. No se implementó `_fetch_geometry` (sin query determinista expediente→polígono).
- **Limitaciones:** visor orientado a consulta ciudadana; datos en servicios propietarios; sede sin geometría; PDFs sin georreferencia sistemática.

## Limitaciones generales

- Sede `sede.pontevedra.gal` muy lenta / no scrapeable de forma fiable en CI cloud.
- Licencias: solo páginas informativas de trámites.
- Nombres de documentos SIOTUGA en gallego/castellano mixto; fechas en `fechaaddef`.

## Adapter

- `municipio/adapters/pontevedra.py` — SIOTUGA + crawl PDF/enlaces WordPress en semillas urbanismo + semillas fijas (Catafis, PXOM, trámites licencias).
