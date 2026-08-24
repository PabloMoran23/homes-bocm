# Alfafar — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `alfafar` |
| INE | 46022 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alfafar.es | Operativa — Drupal 10 portalesmunicipales.es |
| Transparencia | https://www.alfafar.es/es/transparencia | Operativa — enlaces sede y transparenciadana |
| Transparenciadana | https://www.alfafar.es/es/transparenciadana | Operativa — secciones LGT (obras públicas, normativa) |
| Obras públicas | https://www.alfafar.es/es/transparenciadana/obras-publicas | Operativa — PDF proyectos DANA |
| Normativa elaborada | https://www.alfafar.es/es/transparenciadana/normativa-elaboracion | Operativa |
| Sede electrónica | https://alfafar.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://alfafar.sedelectronica.es/board | Operativa — tabla HTML preview-document |
| Catálogo trámites | https://alfafar.sedelectronica.es/dossier | Lento / timeout intermitente en CI |
| Consulta expedientes | https://alfafar.sedelectronica.es/expedientes | Requiere autenticación |
| Visor municipal | https://visor.alfafar.es/es/ | Inaccesible desde CI (timeout) |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia ICV) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede — filas HTML con expediente, procedimiento, PDF preview |
| Planeamiento | ICV WFS zonificación + tablón (IATE, aprobaciones) |
| Transparencia | Portal transparenciadana (obras públicas, normativa) |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Tablón sede (agosto 2026)

- **Urbanismo / Licencias de Actividad:** modificación sustancial LAM (exp. 9187/2026)
- **Urbanismo / Planeamiento:** Acuerdo IATE Sector 2 SU Font Baixa — DOGV (exp. 1300/2019)

## Cómo se publican licencias

- Edictos de licencias y actividades en tablón sede (`preview-document/...`)
- Sin dataset histórico de concesiones con coordenadas
- Trámites vía sede (requiere identificación para consulta expedientes)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46022` (4 instrumentos únicos con polígonos)
  - Visor municipal: `https://visor.alfafar.es/es/` (no accesible desde agente CI)
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci` (p. ej. «SECTOR 2» → «HOMOLOGACIÓN Y PLAN PARCIAL, SECTOR 2»)
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela catastral ni licencia individual
  - Visor municipal inaccesible (timeout); sin API ArcGIS pública identificada
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - Sede con certificado SSL caducado (`insecure_ssl: true`)

### Instrumentos ICV (cod_ine_mun=46022)

| Expediente | Denominación | Clasificación |
|------------|--------------|---------------|
| 19900330 | Plan general | SU |
| 19930108 | MODIFICACIÓN POLIGONO 3 DEL PLAN PARCIAL S-1 ORBA | SUZ |
| 20000695 | HOMOLOGACIÓN Y PLAN PARCIAL, SECTOR 2 | SUZ |
| 20070830 | DOCUMENTO JUSTIFICATIVO DE INTEGRACIÓN TERRITORIAL Y PLAN PARCIAL SECTOR | SUZ |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST de expedientes urbanísticos públicos
- Escaneo ICV WFS completo ~2 min (28 páginas × 500 features); cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`Alfafar`); manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.alfafar:AlfafarAyuntamientoAdapter`
- Fuentes: tablón sede + ICV WFS zonificación + páginas transparenciadana informativas
