# Alboraya — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `alboraya` |
| INE | 46013 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.alboraya.es | Drupal portalesmunicipales — timeout desde CI |
| Transparencia | https://alboraya.governalia.es | Operativa — WordPress Governalia (pocas páginas) |
| Tablón SITAE | https://alborayasitae.sede.gva.es/sitae/ | Operativa — NovaSoft SITAE (GVA) |
| Edictos históricos | https://alborayasitae.sede.gva.es/sitae/VisualizarEdictoPublicoFrontAction.do?accion=historicoEdictos&filtrar=s | Operativa — ~86 anuncios paginados |
| Edictos en vigor | https://alborayasitae.sede.gva.es/sitae/VisualizarEdictoPublicoFrontAction.do?accion=edictosVigor | Operativa |
| Sede electrónica | https://alboraya.sede-virtual.es | Geo-block CloudFront desde CI (403) |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón SITAE — departamento «Gestión y control urbanístico»; edictos art. 55 Ley 6/2014 |
| Planeamiento / IP | SITAE — consultas públicas, estudios integración paisajística, resoluciones |
| Trámites | Sede virtual (sede-virtual.es) — sin listado histórico público accesible |
| Web municipal | Drupal — sección transparencia (inaccesible desde agente CI) |

### Tablón SITAE (septiembre 2026)

- **Histórico:** 86 edictos en 9 páginas (`d-2486328-p=N`)
- **Urbanismo:** 11 edictos en departamento «Gestión y control urbanístico»
- **En vigor:** 1 edicto urbanístico activo
- Estructura HTML: tabla `FilaImpar`/`FilaPar`, columnas tipo/departamento/fechas, PDF `DescargarAnuncioRetirado.do?codigo=EDICTO-L046013-...`

## Cómo se publican licencias

- Edictos de información pública de actividades (art. 55 Ley 6/2014) en SITAE
- Sin dataset histórico de concesiones con coordenadas
- Trámites de licencia vía sede virtual (requiere identificación; geo-block en CI)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46013` (filtro en cliente; CQL del WFS no es fiable)
  - Visor GVA: capa `spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON en rango startIndex 109500–118000 (datos Alboraia al final del dataset ICV); matching textual título SITAE↔`denominaci` ICV
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela ni licencia individual
  - WFS ICV no admite CQL fiable; hay que paginar hasta ~índice 110000 para localizar cod_ine_mun=46013
  - Web municipal y sede virtual inaccesibles desde CI (timeout / geo-block)
  - SITAE sin campo expediente urbanístico en detalle; solo código edicto
  - Escaneo ICV WFS completo ~2 min; cache en memoria por ejecución

### Instrumentos ICV destacados (cod_ine_mun=46013)

| Expediente | Denominación |
|------------|--------------|
| 19980967 | Plan general |
| 20011194 | PLAN PARCIAL SECTOR C - 16 |
| — | Homologación y plan parcial sector Patacona |
| — | Modificación puntual nº 17 plan general |
| — | Plan de acción territorial PATIVEL |

## Limitaciones generales

- `www.alboraya.es`: timeout >20s desde agente cloud
- `alboraya.sede-virtual.es`: CloudFront bloquea acceso por país en CI
- Governalia: solo páginas legales/portada; sin sección urbanismo explícita
- Provincia en `queue.yaml` incorrecta (`Alboraya`); manifest usa `Valencia`

## Adapter implementado

`municipio/adapters/alboraya.py` — SITAE tablón + ICV WFS geometría partial.
