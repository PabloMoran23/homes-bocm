# Marbella — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `marbella` |
| Provincia | Málaga |
| CCAA | Andalucía |
| Población | ~150k |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal información pública | https://informacionpublica.marbella.es/ |
| Ámbito Urbanismo y Ecología | https://informacionpublica.marbella.es/ambitos/urbanismo-y-ecologia.html |
| Planeamiento (listado) | https://informacionpublica.marbella.es/ambitos/urbanismo-y-ecologia/planeamiento.html |
| Infraestructuras (listado) | https://informacionpublica.marbella.es/ambitos/urbanismo-y-ecologia/infraestructuras.html |
| RSS ámbito urbanismo | https://informacionpublica.marbella.es/ambitos/urbanismo-y-ecologia.feed?type=rss |
| Delegación de Urbanismo | https://urbanismo.marbella.es/ |
| Sede electrónica (tablón) | https://marbella.sedelectronica.es/board |
| Sede — trámites | https://marbella.sedelectronica.es/dossier |
| Sede — expedientes (login) | https://marbella.sedelectronica.es/expedientes |
| PGOM (nuevo plan) | https://nuevoplan.marbella.es/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** Joomla 4/5 + plantilla YOOtheme en `informacionpublica.marbella.es` y `urbanismo.marbella.es`.
- **Listados:** tarjetas con enlace `/ambitos/urbanismo-y-ecologia/{planeamiento|infraestructuras}/<slug>.html`, título con número de expediente (`39848/2024`, etc.) y fecha “Publicado el …”.
- **RSS/Atom:** feed por ámbito (`*.feed?type=rss`) con título, enlace, categoría y `pubDate`.
- **Sede:** tablón espublico gestiona (HTML tabla `class_name`, `class_folderCode`, enlaces `/preview-document/<uuid>`). Mezcla presupuestos, subvenciones y urbanismo; el adapter filtra por palabras clave.
- **Expedientes individuales:** páginas Joomla con documentos enlazados (a menudo validación CSV en sede provincial); no hay API JSON pública.

## Licencias de obra

- No hay dataset ni listado histórico abierto de licencias concedidas.
- Tramitación vía sede (`/dossier`) y consulta de expediente con certificado (`/expedientes`).
- El tablón puede publicar edictos puntuales de licencias/actividad; no es un registro completo.
- Instrucción interna publicada en urbanismo.marbella.es sobre agilización de licencias (informativa).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - **SITMA / eVisorWebGIS:** https://sit.marbella.es/eVisorWebGIS/ (SPA Angular; enlace desde urbanismo.marbella.es al visor PGOM). Orientado a consulta interactiva, sin API REST documentada por expediente.
  - **ArcGIS REST** en `https://sit.marbella.es/arcgis/rest/services` — capas de callejero, catastro 2010 (`v_catastro2010_parcelas`), infraestructuras, etc. No hay capa pública con campo de expediente urbanístico enlazable al listado del portal de información pública.
  - **Storymaps** puntuales (p. ej. sectores PGOU) sin servicio query por código de expediente.
  - **Junta de Andalucía SITUA** — consulta provincial genérica; no sustituye geometría por expediente municipal.
- **Estrategia adapter:** ingestar metadatos (título, expediente, URL, fecha) sin `geom_geojson`; el orquestador aplica centroide municipal + jitter.
- **Limitaciones:** visor SITMA sin backend query público por `nº expediente`; publicaciones son PDF/HTML sin georreferencia; sede con login para expedientes.

## Limitaciones generales

- Paginación en listados Joomla (solo primeras páginas en RSS + HTML semilla).
- Muchas entradas del feed global no son urbanismo (presupuestos) — filtro en adapter.
- SSL válido en dominios principales; sede con mismo patrón espublico que otros municipios andaluces.

## Referencia implementación

- Adapter: `municipio/adapters/marbella.py` (`MarbellaAyuntamientoAdapter`)
- Patrón similar: `conil_de_la_frontera.py` (tablón + web), RSS como en adaptadores con `tablon_rss`.
