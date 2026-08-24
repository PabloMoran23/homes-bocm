# Alfara del Patriarca — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://alfaradelpatriarca.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://alfaradelpatriarca.sedelectronica.es/board | ~10 edictos recientes; sin licencias urbanísticas en el momento de la investigación |
| Portal transparencia | https://alfaradelpatriarca.sedelectronica.es/transparency | Sección 7 «Urbanisme, obres públiques i medi ambient» (7 documentos; navegación AJAX) |
| Catálogo trámites | https://alfaradelpatriarca.sedelectronica.es/dossier | Trámites licencias/DR (timeout intermitente en CI) |
| Web corporativa | https://www.alfaradelpatriarca.es | Drupal/adaptive theme; **timeout en CI** |
| Urbanismo web | https://www.alfaradelpatriarca.es/es/pagina/urbanismo | PGOU, plan parcial ARR-2, reforma interior San Diego |
| ICV / visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Zonificación planeamiento CV |

## Cómo se listan expedientes

- **Tablón sede:** tabla HTML con columnas `class_name`, `class_description`, enlaces `/preview-document/{uuid}`.
- **Transparencia sede:** árbol de categorías Wicket AJAX; la sección urbanismo indica 7 documentos pero requiere sesión JS para expandir.
- **Web urbanismo:** página estática con bloques por instrumento (PGOU, plan parcial, reforma interior) y PDFs enlazados.
- **ICV WFS:** capa `ms:Planeamiento.Zonificacion` en `terramapas.icv.gva.es/0702_Planeamiento`; filtro por `cod_ine_mun=46025` (client-side; CQL del servicio no filtra correctamente).

### Instrumentos ICV identificados (cod_ine_mun 46025)

| Expediente | Denominación | Polígonos WFS |
|------------|--------------|---------------|
| 19981541 | Plan general (PGOU) | 34 |
| 20030478 | Plan parcial Sector ARR-2 | 3 |
| 20060272 | Plan de Reforma Interior Sector San Diego | 1 |

## Cómo se publican licencias

- No hay dataset histórico de licencias concedidas en abierto.
- El tablón actual solo contiene edictos presupuestarios, fiscales y subvenciones.
- Las licencias se tramitan vía sede (`/dossier`) y se publican puntualmente en tablón cuando procede.
- El adapter incluye páginas informativas de tablón, catálogo y transparencia (patrón Pozuelo/Enguera).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:Planeamiento.Zonificacion`
  - Campo expediente: `expediente` (p. ej. `19981541`)
  - Query geometría: `GetFeature` con `featureId=Planeamiento.Zonificacion.{id}` + `outputFormat=application/json; subtype=geojson` + `srsName=EPSG:4326`
  - Visor: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
- **Estrategia:** 3 filas de proyecto (PGOU, plan parcial ARR-2, reforma interior San Diego) con polígonos fusionados por expediente desde ICV WFS. Tablón/transparencia sin geometría enlazable.
- **Limitaciones:**
  - CQL_FILTER del WFS no funciona (devuelve municipios incorrectos); se usan `featureId` precalculados.
  - Web corporativa inaccesible desde CI (timeout); scrape best-effort con timeout corto.
  - Transparencia sede requiere AJAX Wicket para listar PDFs.
  - Licencias del tablón sin georreferencia.

## Limitaciones generales

- Boletín DOGV: 2 entradas históricas en cola (`dogv`).
- Provincia en `queue.yaml` incorrecta (`Alfara del Patriarca`); manifest usa `Valencia`.
- INE municipio: **46025** (no confundir con 46024 = Alfara de la Baronia en ICV).
