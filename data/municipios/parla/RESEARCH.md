# Parla — investigación portal ayuntamiento

## Resumen

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Portal transparencia | https://transparencia.ayuntamientoparla.es/obras-publicas-y-urbanismo/ | WordPress (oGov) | **Principal** — PDFs planeamiento general, desarrollo, PGOU |
| Sede STA catálogo | https://sede.ayuntamientoparla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | STA + JSON embebido `dataset_CATSERV` | Trámites urbanismo (licencias) |
| Sede tablón | https://sede.ayuntamientoparla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON | STA AJAX (`submitAjax.aa`) | Secundario — sin dataset en HTML inicial |
| Listado licencias | https://transparencia.ayuntamientoparla.es/obras-publicas-y-urbanismo/expedientes-de-licencias-de-obras/ | PDF único (2020) | Histórico licencias concedidas |
| Visor SIT CM | https://idem.madrid.org/cartografia/sitcm/html/visor.htm?municipio=106 | Visor regional Comunidad de Madrid | Consulta PGOU municipal (no por expediente) |

## Páginas semilla (proyectos)

- `.../planeamiento-general/` — PGOU 1997, planes de sectorización (53 PDFs)
- `.../planeamiento-de-desarrollo/` — planes parciales, especiales (173 PDFs)
- `.../planeamiento-de-desarrollo-2/` — planeamiento en exposición pública (21 PDFs)
- `.../plan-general-de-ordenacion-urbana/` — PGOU vigente y modificaciones (19 PDFs)

Total aproximado: **~260 documentos PDF** enlazados en HTML (sin duplicar entre páginas).

## Licencias

- **No hay** listado tabular actualizado de concesiones con coordenadas.
- Transparencia publica un único PDF `EXPEDIENTES-LICENCIAS-OBRA-2020.pdf` (pestaña 2020).
- Catálogo sede incluye **22 trámites** con keyword `URB` (licencia de obra, declaración responsable, certificados, etc.) en `dataset_CATSERV`.
- Expedientes abiertos requieren identificación en sede (`EXPEDIENTES_FULL`).

## Proyectos / expedientes

- Documentación urbanística estática en transparencia (memorias, planos, acuerdos, estudios).
- No hay API REST de posts filtrada por urbanismo; el scrape recorre las páginas semilla y extrae enlaces `wp-content/uploads/*.pdf`.
- Títulos desde texto del enlace HTML o nombre de fichero; fechas inferidas de ruta `/uploads/AAAA/MM/`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor SIT de la Comunidad de Madrid (`municipio=106` = Parla), enlazado desde sede (`PTS2_ORDENANZA`) y transparencia. Muestra clasificación/calificación del PGOU regional, no geometría por expediente del ayuntamiento.
- **Estrategia:** No hay MapServer/ArcGIS municipal ni WFS con campo de expediente. Los planos están en PDF sin georreferencia machine-readable. El orquestador usará centroide municipal + jitter.
- **Limitaciones:** Sin visor urbanístico propio del ayuntamiento; tablón y expedientes sin enlace GIS; listado de licencias solo en PDF 2020.

## Limitaciones técnicas

- `www.ayuntamientoparla.es` bloquea bots (WAF); se usa transparencia y sede.
- Tablón STA Parla no expone `dataset_PTS2_TABLON` en HTML (a diferencia de Getafe/Fuenlabrada); requiere sesión AJAX.
- SSL sede: `sede_insecure_ssl: true` por compatibilidad con cadena STA.

## Adapter implementado

- Módulo: `municipio.adapters.parla:ParlaAyuntamientoAdapter`
- Estrategia: crawl PDFs transparencia + trámites URB del catálogo sede + registro del listado PDF 2020.
