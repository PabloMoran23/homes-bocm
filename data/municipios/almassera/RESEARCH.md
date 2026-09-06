# Almàssera — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `almassera` |
| INE | 46014 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.almassera.es | Operativa — Drupal 10 portalesmunicipales (DigitalValue) |
| Transparencia | https://www.almassera.es/es/transparencia | Operativa — enlaces LGT |
| Normativa urbanística | https://www.almassera.es/es/transparencia/35-normativa-urbanistica-planes-parciales | Operativa (lenta) |
| PUAM | https://www.almassera.es/es/transparencia/38-plan-urbano-actuacion-municipal-almassera | Operativa |
| Formularios urbanismo | https://www.almassera.es/es/content/impresos-solicitudes-urbanismo | Operativa — PDFs licencias |
| Bando municipal | https://www.almassera.es/es/servicios/canal-bando-municipal | Operativa |
| Sede electrónica | https://almassera.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://almassera.sedelectronica.es/board | Operativa — ~10 filas HTML preview-document |
| Catálogo trámites | https://almassera.sedelectronica.es/dossier | Operativa |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede — filas HTML con preview-document (sin urbanismo en muestra sept 2026) |
| Planeamiento | ICV WFS zonificación + transparencia (normativa, PUAM) |
| Trámites | Formularios PDF en web + catálogo sede / dossier |

### Tablón sede (septiembre 2026)

- Anuncios administrativos recientes (padrón, empleo, junta de gobierno)
- Sin filas de licencias/urbanismo en las ~10 entradas visibles

## Cómo se publican licencias

- Formularios descargables en web (`impresos-solicitudes-urbanismo`): licencia obra mayor/menor, apertura, actividades
- Edictos potenciales en tablón sede y canal bando municipal
- Sin dataset histórico público de concesiones con coordenadas
- Trámites vía sede (consulta expedientes requiere identificación)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46014` (1 instrumento con polígono)
  - Visor GVA: capa `spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci`
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/plan parcial, no parcela ni licencia individual
  - Sin visor municipal propio identificado
  - Web corporativa muy lenta desde CI (timeouts >120s en algunas páginas)
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - Sede con certificado SSL caducado (`insecure_ssl: true`)

### Instrumentos ICV (cod_ine_mun=46014)

| Expediente | Denominación |
|------------|--------------|
| 20001443 | Homologación y plan parcial SR-1 |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST de expedientes urbanísticos públicos
- Escaneo ICV WFS completo ~2 min (30 páginas × 500 features); cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`Almàssera`); manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.almassera:AlmasseraAyuntamientoAdapter`
- Fuentes: tablón sede + ICV WFS zonificación + transparencia web + páginas informativas trámites
