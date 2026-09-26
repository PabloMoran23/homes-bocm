# Massanassa — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `massanassa` |
| INE | 46165 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## Fuentes

### Web municipal (Drupal portalesmunicipales)

- Base: https://www.massanassa.es
- Urbanismo y medio ambiente (normativa): https://www.massanassa.es/es/pagina/urbanismo-medio-ambiente
  - PGOU 1989 (PDF `ALC-030-1989_sp.pdf`)
  - Modificaciones normas urbanísticas (BOP-221/2025, BOP-1/2026)
  - Planes parciales El Divendres y Primer Braç
  - Reparcelación / urbanización calle Maestrat (edictos PDF)
  - Ordenanzas licencias edificación y DR (URB-035/038)
- Urbanismo (convocatorias): https://www.massanassa.es/es/pagina/urbanismo
- Visor cartografía GVA (enlace footer): https://visor.gva.es/visor/?extension=722720,4364478,726100,4366348&nivelZoom=16

### Sede electrónica (espublico gestiona)

- Base: https://massanassa.sedelectronica.es
- Tablón de anuncios: https://massanassa.sedelectronica.es/board
  - HTML tabla Wicket; ~10 filas visibles (sin paginación AJAX en scrape estático)
  - Actualmente mayoría anuncios padrón; licencias/urbanismo cuando se publican
- Trámites / catálogo: https://massanassa.sedelectronica.es/dossier
- Consulta expedientes: https://massanassa.sedelectronica.es/expedientes (requiere identificación)
- Carpeta tributaria ICIO: https://portaltributario.massanassa.es (autoliquidación obras, sin listado histórico)

### ICV / GVA — planeamiento

- WFS zonificación: `https://terramapas.icv.gva.es/0702_Planeamiento`
- TypeName: `Planeamiento.Zonificacion`
- Filtro cliente: `cod_ine_mun=46165` (11 polígonos, 3 instrumentos)
- Instrumentos: Plan general (19890579), Homologación Suelo Industrial (19971068), Homologación Sector El Divendres (19970876)
- GeoJSON: `outputFormat=application/json; subtype=geojson`, `srsName=EPSG:4326`
- Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Licencias | Tablón sede (edictos cuando publicados) + trámites sede / ordenanzas PDF |
| Planeamiento | Normativa web (PDFs) + capas ICV WFS (zonificación PGOU/homologaciones) |
| Reparcelación | Edictos PDF en web (calle Maestrat) |

## Cómo se publican licencias

- Edictos en tablón sede cuando procede información pública
- No hay dataset histórico de concesiones público
- Trámites vía sede electrónica y ordenanzas URB-035/038 (DR y licencias edificación)
- ICIO autoliquidación en portaltributario (sin coordenadas)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV WFS `Planeamiento.Zonificacion` (`cod_ine_mun=46165`); visor cartografía GVA (enlace web municipal)
- **Estrategia:** zonas de planeamiento vía WFS paginado + matching textual título↔`denominaci` para enriquecer tablón/normativa; 3 instrumentos con polígonos MultiPolygon
- **Limitaciones:** sin visor municipal propio (solo GVA); geometría ICV es zonificación PGOU/SUZ, no parcela catastral; tablón sin edictos urbanísticos recientes; consulta expedientes requiere login; sede requiere `insecure_ssl` en CI

## Limitaciones generales

- Tablón: pocas filas urbanísticas en el momento del scrape (mayoría padrón)
- Sin API REST de expedientes urbanísticos públicos
- ICV WFS requiere paginación (~12k features) para filtrar por municipio
- SSL sede: certificado intermitente en algunos entornos → `insecure_ssl: true`
