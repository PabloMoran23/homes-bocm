# Riba-roja de Túria — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `riba-roja-de-turia` |
| INE | 46214 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | Sin boletín asociado en cola |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.ribarroja.es | Operativa — Drupal 11 portalesmunicipales (Dival) |
| Tablón de anuncios | https://www.ribarroja.es/es/ayuntamiento/tablon_de_anuncios | Operativa — listado `portales7-weblink` (~50 enlaces) |
| Oficina virtual | https://oficinavirtual.ribarroja.es/PortalCiudadania/ | Operativa — sede propia (certificado digital) |
| Trámites URB | https://oficinavirtual.ribarroja.es/PortalCiudadania/tramites/browser.do?formAction=btList&s=11 | Catálogo URB 01–13 |
| Tablón edictos sede | https://oficinavirtual.ribarroja.es/PortalCiudadania/tablonEdictos.do | Iframe; no listado HTML scrapeable |
| Planeamiento en vigor | https://www.ribarroja.es/planeamiento_en_vigor/planeamiento_de_desarrollo | PDF sectores desarrollo |
| Transparencia urbanismo | https://www.ribarroja.es/es/portal_de_transparencia/transparencia_urbanismo_obras_publicas_medioambiente | PGOU, convenios, obras |
| Urbanismo | https://www.ribarroja.es/es/seccion/urbanisme | Sección municipal |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Referencia ICV |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Anuncios / IP | Tablón web Drupal (`field__item` enlaces a `/contenidos/…`) |
| Planeamiento | Sección planeamiento en vigor + transparencia + noticias |
| Trámites | Oficina virtual URB (formularios; sin expediente público) |

Detalle tablón: páginas de contenido con `field-fecha-visible` (`datetime` ISO).

## Cómo se publican licencias

- Trámites URB 02–05 (licencias tipo I/II, DR, primera ocupación) vía oficina virtual
- Criterios interpretativos licencias publicados en tablón web (normativa, no concesiones)
- Sin registro histórico público de licencias concedidas con dirección/coords
- Tablón edictos sede en iframe (no scrapeable con urllib)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro: `cod_ine_mun=46214`
  - Visor GVA: capa `spaicv0702_plan_zonificacion`
- **Estrategia:** paginado WFS GeoJSON; matching título tablón ↔ `denominaci` (sectores Masía San Rafael, PI-6 Peyland, PGOU, etc.)
- **Limitaciones:**
  - Polígonos ICV = zonificación PGOU/planes parciales, no parcela ni licencia individual
  - Sede propia sin API pública de geometría de expediente
  - Tablón edictos sede no accesible en HTML plano

### Instrumentos ICV (muestra)

| Denominación | Tipo |
|--------------|------|
| Plan general | PGOU |
| Homologación plan parcial sector PI-6 Peyland | plan parcial |
| Homologación modificación y plan parcial Masía de Baló | plan parcial |

## Limitaciones generales

- No hay sede espublico gestiona (`*.sedelectronica.es/board` no operativo para este municipio)
- Escaneo ICV WFS lento (~offsets 0–13500)
- Tablón mezcla empleo/subvenciones; filtro regex urbanismo

## Adapter implementado

- `municipio.adapters.riba_roja_de_turia:RibaRojaDeTuriaAyuntamientoAdapter`
