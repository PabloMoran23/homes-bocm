# Gata de Gorgos — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `gata-de-gorgos` |
| INE | 03071 |
| Provincia | Alicante |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.gatadegorgos.org | Operativa — WordPress |
| Planejament | https://www.gatadegorgos.org/ajuntament/planejament/ | Operativa — enlace GVA |
| Sol·licituds i impresos | https://www.gatadegorgos.org/ajuntament/solicituds-i-impresos/ | Operativa — formularis urbanisme 2026 |
| Tauler d'anuncis (WP) | https://www.gatadegorgos.org/category/noticies/tauler-danuncis/ | Operativa — categoría noticias |
| Sede electrónica | https://gatadegorgos.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://gatadegorgos.sedelectronica.es/board | Operativa — tabla HTML preview-document (~10 filas) |
| Catálogo trámites | https://gatadegorgos.sedelectronica.es/dossier | Operativa (lento en CI) |
| Consulta expedientes | https://gatadegorgos.sedelectronica.es/expedientes | Requiere autenticación |
| Transparencia sede | https://gatadegorgos.sedelectronica.es/transparency/8f1eda8f-20b0-412b-bfdf-24fdf4970950/ | Operativa |
| Registro GVA planeamiento | https://politicaterritorial.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03071%20GATA%20DE%20GORGOS/ | Operativa — índice Apache PGOU + P. diferido |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia zonificación |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede (edictos recientes) + formularios web/sede |
| Planeamiento | ICV WFS + registro GVA (carpetas PGOU/NNSS) + página planejament |
| Anuncios | Categoría WordPress `tauler-danuncis` |
| Trámites | Catálogo sede / dossier (sin histórico público de concesiones) |

### Tablón sede (agosto 2026)

Sin anuncios urbanísticos en las ~10 filas visibles (presupuesto, personal, pleno, residuos).

### Instrumentos ICV (cod_ine_mun=03071)

| Expediente | Denominación |
|------------|--------------|
| 00000000 | NORMAS SUBSIDIARIAS |
| 19991221 | HOMOLOGACIÓN Y PLAN PARCIAL, UA 6-VIII |
| 20042236 | MODIFICACIÓN PUNTUAL N. 9 DE LA NORMAS SUBSIDIARIAS |
| 20110420 | Plan de Reforma Interior Sector "PLANS" |

## Cómo se publican licencias

- Edictos en tablón sede (`preview-document/...`) cuando hay convocatoria
- Formularios «Promptuari d'autoritzacions urbanístiques 2026» en web y sede
- Sin dataset histórico de concesiones con coordenadas
- Consulta expedientes vía sede (requiere identificación)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=03071` (4 instrumentos con polígonos)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON (~14k features); matching textual título↔`denominaci`; instrumentos ICV como filas de proyectos con `geom_geojson`
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela ni licencia individual
  - Sin visor municipal propio identificado
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - WordPress REST API bloqueada en CI (WAF); scrape HTML de categoría
  - Escaneo ICV WFS ~2 min por ejecución (cache en memoria)

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST pública de expedientes urbanísticos
- Provincia en `queue.yaml` incorrecta (`Gata de Gorgos`); manifest usa `Alicante`
- GVA reg-planeamiento: índice de carpetas/PDFs (no metadatos estructurados)

## Adapter implementado

- `municipio.adapters.gata_de_gorgos:GataDeGorgosAyuntamientoAdapter`
- Fuentes: tablón sede + WordPress tauler + registro GVA + ICV WFS + páginas informativas trámites
