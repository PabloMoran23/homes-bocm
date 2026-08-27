# Chiva — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `chiva` |
| INE | 46100 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.chiva.es | Operativa — Drupal 10 portalesmunicipales.es |
| Urbanismo | https://www.chiva.es/urbanismo | Operativa — Chiva Urban LAB (PUAM, ordenanzas) |
| Normas urbanísticas | https://www.chiva.es/transparencia/normas-urbanisticas | Operativa — PGOU planos ZIP, NNSS, ordenanzas |
| Documentos tramitación | https://www.chiva.es/transparencia/documentos-tramitacion | Operativa — PAM/PTM memorias y planos |
| Urbanizaciones | https://www.chiva.es/seccion/urbanizaciones | Operativa — Calicanto, Olímar, etc. |
| Impresos | https://www.chiva.es/impresos | Operativa — URB*/ACT* licencias y DR |
| Sede electrónica | https://chiva.sedelectronica.es | Operativa — espublico gestiona (`insecure_ssl`) |
| Tablón de anuncios | https://chiva.sedelectronica.es/board | Operativa — 10 filas visibles (ago 2026 sin urbanismo) |
| Portal transparencia sede | https://chiva.sedelectronica.es/transparency | Operativa |
| Consulta expedientes | https://chiva.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia ICV |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias / actividades | Tablón sede (preview-document) + impresos web (URB/ACT) |
| Planeamiento | Transparencia normas + documentos tramitación (PDF/ZIP) |
| Urbanizaciones | Sección web + noticias |
| Trámites | Sede dossier / impresos (sin histórico público de concesiones) |

### Tablón sede (agosto 2026)

- 10 anuncios recientes: subvenciones deportivas, premios cultura — **sin filas urbanismo/licencias** en scrape estático Wicket.

## Cómo se publican licencias

- Impresos URB/ACT en www.chiva.es (solicitudes, DR, comunicaciones)
- Edictos potenciales en tablón sede (ninguno urbanístico en ventana actual)
- Sin dataset histórico de concesiones con coordenadas
- Consulta expedientes vía sede (autenticación obligatoria)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46100` (1 instrumento: Plan general exp. 19980265)
  - InventarioSuSuz: 4 polígonos SU/SUZ sin denominación en propiedades
  - ZIP cartografía municipal en normas urbanísticas (`TerminoMunicipal.zip`, `CascoUrbano.zip`, etc.) — no integrado en adapter
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci` del PGOU
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU, no parcela ni licencia individual
  - Tablón paginado Wicket (~10 filas sin AJAX)
  - Sede con certificado SSL caducado (`insecure_ssl: true`)
  - Sin visor municipal ArcGIS identificado

### Instrumentos ICV (cod_ine_mun=46100)

| Expediente | Denominación | Clasificación |
|------------|--------------|---------------|
| 19980265 | Plan general | PGOU municipal |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios)
- Sin API REST de expedientes urbanísticos públicos
- Escaneo ICV WFS ~2 min (paginado hasta offset 3000+)
- Provincia en `queue.yaml` incorrecta (`Chiva (Valencia)`); manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.chiva:ChivaAyuntamientoAdapter`
- Fuentes: tablón sede + ICV WFS + transparencia PDFs + impresos licencias
