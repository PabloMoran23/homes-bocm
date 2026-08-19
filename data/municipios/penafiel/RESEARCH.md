# Peñafiel — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `penafiel` |
| Provincia | Valladolid (CYL código 47, municipio 147) |
| Boletín | BOCYL (`bocyl`) |
| CMS web | PHP propio (Plesk/nginx) |
| Sede | espublico gestiona (`penafiel.sedelectronica.es`) |

## URLs base y semillas

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.penafiel.es | Portal institucional PHP |
| Urbanismo | https://www.penafiel.es/urbanismo.php | PGOU, PECH, subvenciones rehabilitación (PDFs en `/adjuntos/`) |
| Sede electrónica | https://penafiel.sedelectronica.es | Trámites, tablón, transparencia |
| Tablón anuncios | https://penafiel.sedelectronica.es/board | Anuncios BOPVA (Wicket HTML) |
| Catálogo trámites | https://penafiel.sedelectronica.es/dossier | 111 trámites (requiere cookie de `/info`) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=147 | Planeamiento en información pública |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=147 | Archivo planeamiento aprobado |

## Expedientes / proyectos

### Web `urbanismo.php`

- HTML estático con pestañas (`filterDiv`) y carpetas (`carpeta`) por instrumento.
- **Plan Especial Conjunto Histórico (PECH):** memorias, planos DO-PO, aprobación BOCYL 2022.
- **Plan General de Ordenación Urbana (PGOU):** índice de planos PO-1 … PO-4 (PDFs).
- Sin listado de expedientes individuales ni API; solo documentación normativa.

### Sede espublico — tablón

- Tabla HTML con `preview-document/{uuid}` por fila.
- Ejemplos urbanísticos (2026): declaración de ruina (c/ Las Damas), aprobación inicial modificación puntual PECH (Avda. Constitución 40).
- Categorías: Declaraciones de Ruina, Urbanismo, etc.
- Paginación limitada en portada; sin API JSON pública.

### Junta CYL PlanPublica

- Buscador por municipio; sin filas indexables vía scrape estático en el momento de la investigación (portal AJAX).
- Semilla registrada para cruce manual / futuras mejoras.

## Licencias

- **Tablón:** no hay concesiones de licencia de obra publicadas en el extracto visible (sí ordenanzas fiscales, subvenciones, ruina).
- **Catálogo sede:** trámites informativos de licencia urbanística, obra, ocupación, actividad, ruina, etc. (páginas `/catalog/t/...`).
- **Web urbanismo:** texto descriptivo de tipos de expediente (licencias mayor/menor, comunicaciones ambientales) sin listado de concesiones.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes consultadas:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales` — filtro `n_mun ILIKE '%PENAFIEL%'` → **0 features**
  - Web municipal y sede: sin visor ArcGIS/WFS enlazado a expedientes
  - PGOU/PECH solo en PDF raster
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`manifest.centroid` ≈ 41.5983, -4.1189)
- **Limitaciones:** sin GIS público municipal ni capas IDECyL para este término; geometría de ámbito no recuperable de forma determinista

## Limitaciones

- `/dossier` devuelve redirect infinito sin cookie previa de `/info` (manejado en adapter).
- Tablón mezcla anuncios no urbanísticos (hacienda, fiestas, subvenciones cultura).
- PlanPublica requiere sesión JS/AJAX para listar documentos.
- Sin visor urbanístico ni WFS con polígonos para Peñafiel en IDECyL.
