# Torrent — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `torrent-46244` |
| INE (ICV) | 46244 |
| Provincia | Valencia |
| CCAA | comunitat-valenciana |
| Boletín | Sin boletín asociado en cola BOCM |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://torrent.es | Operativa — WordPress + Elementor |
| Urbanismo | https://torrent.es/urbanismo-y-vivienda/ | Operativa |
| Planeamiento | https://torrent.es/urbanismo-y-vivienda/planeamiento/ | Operativa — PGOU, PP, PRI, estudios detalle |
| Tablón urbanismo web | https://torrent.es/urbanismo-y-vivienda/tablon-de-anuncios-urbanismo/ | Operativa — PDFs información pública |
| Estado tramitación | https://torrent.es/urbanismo-y-vivienda/planeamiento/estado-tramitacion-planeamiento/ | Operativa |
| Repositorio documentos | https://www.torrent.es/torrentPublic/docroot/repositorio/Serveis%20admin/Urbanisme/ | Operativa — planes parciales PDF |
| Sede electrónica | https://torrent.sedelectronica.es | Operativa — espublico gestiona |
| Tablón sede | https://torrent.sedelectronica.es/board | Operativa — tabla HTML preview-document |
| Trámite licencias URBA-052 | https://torrent.es/tramites/consulta-de-expedientes-de-la-seccion-de-licencias/ | Informativo (consulta expedientes terminados) |
| Geo Urbanismo | https://geo.torrent.es/ | Operativo — visor Neobora/Dielmo (Sencha) |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento / IP | WordPress: secciones planeamiento + tablón urbanismo con enlaces PDF (wp-content + torrentPublic) |
| Licencias | Tablón sede (edictos esporádicos) + trámites sede (sin listado histórico público de concesiones) |
| Consulta expedientes | URBA-052 informativo; sede requiere identificación para expedientes en curso |

### Tablón sede (octubre 2026)

- ~13 filas visibles en HTML estático; mayoría no urbanística (subvenciones, empleo, edictos)
- Filas urbanísticas puntuales (p. ej. urbanización Calicanto)

### Tablón urbanismo web

- PDFs de modificaciones PGOU, PRI Profeta Daniel, planos información pública, certificados acuerdos

## Cómo se publican licencias

- Edictos potenciales en tablón sede (`preview-document/...`)
- Sin dataset histórico de concesiones con coordenadas
- Trámites URBA-115 (licencia edificación), URBA-102 (declaración responsable) vía sede
- Adapter incluye páginas informativas de tablón, catálogo y trámite URBA-052

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName zonificación: `Planeamiento.Zonificacion`
  - TypeName SUZ: `InventarioSuSuz`
  - Filtro municipio: `cod_ine_mun=46244`
  - Visor municipal: `https://geo.torrent.es/` (Neobora; sin servicio WFS/ArcGIS REST público identificado)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci`; enriquecimiento en filas ICV y PDFs con sector/plan en título
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes, no parcela ni licencia individual
  - geo.torrent.es es aplicación Sencha sin API documentada
  - Tablón sede paginado Wicket (pocas filas urbanísticas en scrape estático)
  - PDFs del portal sin georreferencia embebida
  - Sede puede requerir `insecure_ssl: true` según cadena certificado

### Instrumentos ICV (cod_ine_mun=46244, muestra)

| Denominación | Notas |
|--------------|-------|
| Plan general | Zonificación PGOU |
| Modificación puntual plan general nº10 | Instrumento puntual |

## Limitaciones generales

- Sin BOCM asociado en cola (`bocm_count: 0`)
- Crawl WordPress + ICV WFS puede tardar varios minutos (offsets WFS Comunitat Valenciana)
