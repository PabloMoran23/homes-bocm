# Barxeta — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `barxeta` |
| INE | 46045 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.barxeta.es | Operativa — Drupal Digital Value portales |
| PGOU | https://www.barxeta.es/ca/pagina/pla-general-dordenacio-urbana | Operativa — 3 PDFs (catálogo SUSPÉS, normativa, memoria R070913) |
| Sede electrónica | https://barxeta.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://barxeta.sedelectronica.es/board | Operativa — tabla HTML preview-document |
| Transparencia sede | https://barxeta.sedelectronica.es/transparency | Operativa |
| Catálogo trámites | https://barxeta.sedelectronica.es/dossier | Operativa (lento) |
| Consulta expedientes | https://barxeta.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento / PGOU | Web Drupal — PDFs estáticos en `/sites/www.barxeta.es/files/` |
| Zonificación | ICV WFS `Planeamiento.Zonificacion` filtro `cod_ine_mun=46045` |
| Licencias / actividades | Tablón sede — sin licencias urbanísticas recientes (agosto 2026) |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Tablón sede (agosto 2026)

- Sin licencias urbanísticas recientes; mayoría subvenciones y anuncios genéricos
- **Parcelas afectadas obras forestales** (exp. 1245/2025) — procedimiento genérico, anuncio BOP

### PGOU web (R070913)

| Documento | URL |
|-----------|-----|
| Catàleg PGOU (SUSPÉS) | `/files/Catálogo PGOU BARXETA_R070913.pdf` |
| Normativa PGOU | `/files/Normativa PGOU BARXETA_R070913.pdf` |
| Memòria PGOU | `/files/Memoria PGOU BARXETA_R070913.pdf` |

## Cómo se publican licencias

- Edictos potenciales en tablón sede (`preview-document/...`)
- Sin dataset histórico de concesiones con coordenadas
- Trámites vía sede (requiere identificación para consulta expedientes)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46045` (1 instrumento, 7 polígonos de zonificación)
  - Visor GVA: capa `spaicv0702_plan_zonificacion`
- **Estrategia:** query WFS con `CQL_FILTER=cod_ine_mun='46045'`; merge polígonos por `denominaci`+`expediente`; matching textual título↔«Plan general»
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU, no parcela catastral ni licencia individual
  - Sin visor cartográfico municipal propio
  - PGOU suspendido en web; solo documentación PDF sin geometría embebida
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - Sede con certificado SSL caducado (`insecure_ssl: true`)

### Instrumentos ICV (cod_ine_mun=46045)

| Expediente | Denominación | Polígonos WFS |
|------------|--------------|---------------|
| 19981056 | Plan general | 7 (zonas SU/SUZ) |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST de expedientes urbanísticos públicos
- Query ICV WFS con CQL ~50s (dataset completo CV); cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`Barxeta`); manifest usa `Valencia`

## Adapter implementado

`municipio/adapters/barxeta.py` — `BarxetaAyuntamientoAdapter`
