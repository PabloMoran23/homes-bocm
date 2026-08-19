# Enguera — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `enguera` |
| INE | 46118 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## Fuentes

### Web municipal (Adaptive Theme / Drupal)

- Base: https://www.enguera.es
- Trámites y modelos urbanismo: https://www.enguera.es/es/pagina/tramites
  - Declaraciones responsables de obra (suelo urbano)
  - Modelos LMIT / minimización impacto territorial
  - Licencias en suelo no urbanizable (LO.3.1)
- Catálogo procedimientos (enlace a sede): https://www.enguera.es/es/transparencia/catalogo-procedimientos-del-ayuntamiento

### Sede electrónica (espublico gestiona)

- Base: https://enguera.sedelectronica.es
- Tablón de anuncios: https://enguera.sedelectronica.es/board
  - HTML tabla Wicket; paginación AJAX «Mostrar más» (10 filas por página en scrape estático)
  - Categoría **Licencias Urbanísticas** con edictos LMIT (polígono/parcela en título)
  - Procedimientos: `Licencias Urbanísticas`, `Disposiciones Normativas`, etc.
- Trámites / catálogo: https://enguera.sedelectronica.es/dossier
- Transparencia urbanismo (instrumentos planeamiento): https://enguera.sedelectronica.es/transparency/34419a96-975a-48da-bb49-2ec342517cf4/
  - Enlaces a ICV, visor GVA, normas subsidiarias PDF, plan de ordenación de montes

### ICV / GVA — planeamiento

- WFS zonificación: `https://terramapas.icv.gva.es/0702_Planeamiento`
- TypeName: `ms:Planeamiento.Zonificacion`
- Filtro municipio: `cod_ine_mun=46118` (210 polígonos, 7 denominaciones únicas)
- GeoJSON: `outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326`
- Geometría por feature: `featureId=Planeamiento.Zonificacion.{id}` (CQL_FILTER no fiable en este servicio)
- Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / LMIT | Tablón sede — filas HTML con expediente, procedimiento, PDF preview |
| Planeamiento | Transparencia sede + capas ICV WFS (no listado de expedientes IP en web) |
| Trámites | Catálogo sede + formularios PDF en web municipal |

## Cómo se publican licencias

- Edictos de información pública LMIT en tablón (`Licencias Urbanísticas`)
- No hay dataset histórico de concesiones; trámites vía sede (requiere identificación)
- Modelos DR.2 / LMIT en página de trámites web

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS `ms:Planeamiento.Zonificacion` (`cod_ine_mun=46118`); visor cartografía GVA (enlace transparencia)
- **Estrategia:** zonas de planeamiento vía `featureId` en WFS; matching textual título↔`denominaci` para enriquecer tablón; licencias con polígono/parcela sin capa catastral pública enlazada
- **Limitaciones:** tablón paginado (solo primera página sin AJAX); geometría ICV es zonificación PGOU/SPE, no parcela catastral; consulta expedientes en sede requiere login

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST de expedientes urbanísticos públicos
- ICV CSV completo ~5 min (se usa lista fija de 4 zonas + fetch puntual por `featureId`)
