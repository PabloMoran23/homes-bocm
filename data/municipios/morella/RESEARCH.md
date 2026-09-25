# Morella — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica (espublico gestiona) | https://morella.sedelectronica.es | Tablón `/board`, trámites `/dossier`, consulta expedientes (login) |
| Web municipal | https://www.morella.net | Normativa urbanística, oficina de obras (Cloudflare; bloqueo a bots) |
| Transparencia (Governalia) | https://morella.governalia.es/es/ | Contratos y gobierno abierto (sin listado urbanístico detallado) |
| PGOU textos consolidados (GVA) | https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/2.%20Textos%20consolidados,%20Orden%2010-2022/12080%20Morella/ | Índice Apache con PDFs del PGOU (normas, clasificación, zonificación, POP) |
| Visor ICV / WFS planeamiento | https://terramapas.icv.gva.es/0702_Planeamiento | Capas `InventarioSuSuz` y `Planeamiento.Zonificacion`, filtro `cod_ine_mun=12080` |

**Nota:** `www.morella.es` no resuelve (NXDOMAIN). El dominio operativo es `morella.net`.

## Expedientes / proyectos

- **Tablón sede:** HTML tabular (clases `class_name`, `class_folderCode`, …). En septiembre 2026 predominan anuncios de personal, fiscalidad y ordenanzas; sin edictos urbanísticos recientes en la primera página.
- **PGOU:** documentación consolidada publicada por la Generalitat (PDFs por tomo: clasificación, zonificación, sistemas generales, ordenación pormenorizada).
- **GIS ICV:** inventario de sectores/UA del municipio (`InventarioSuSuz`, ~11 registros) y polígonos de zonificación (`Planeamiento.Zonificacion`, ~17 registros) con geometría en WGS84 vía WFS GML.

## Licencias de obra

- No hay dataset público de concesiones históricas.
- Trámites vía sede (`/dossier`) y oficina de obras (web municipal).
- El adapter registra páginas informativas del tablón y catálogo de trámites (patrón Pozuelo/Benigànim).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `https://terramapas.icv.gva.es/0702_Planeamiento` — `InventarioSuSuz` (campo `id`, `pp`, `ue`, `cod_ine_mun`) y `Planeamiento.Zonificacion` (`denominaci`, `zon_suelo`, `expediente`).
- **Estrategia:** paginar WFS, filtrar `cod_ine_mun='12080'`, parsear `gml:posList` → GeoJSON Polygon; query puntual con `CQL_FILTER=id='…'` para `geometry_source_url`.
- **Limitaciones:** web `morella.net` detrás de Cloudflare (sin crawl de avisos Drupal); tablón sin coords; licencias sin georreferencia; PDFs PGOU sin enlace GIS por expediente.

## Limitaciones generales

- Dominio `.es` inexistente; scraping web principal no fiable en CI.
- Tablón sede sin paginación profunda en el HTML inicial (solo ~10 filas visibles).
- Consulta de expedientes requiere Cl@ve.
