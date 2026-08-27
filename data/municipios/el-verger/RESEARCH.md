# El Verger — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `el-verger` |
| INE | 03082 |
| Provincia | Alicante |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.elverger.es | Operativa — WordPress (The Events Calendar, WPML) |
| Urbanismo | https://www.elverger.es/ajuntament/urbanisme/ | Operativa — sección planeamiento |
| Planejament vigent | https://www.elverger.es/ajuntament/urbanisme/planejament-municipal-vigent/ | Operativa — PDFs PGOU, planes parciales, edictos |
| PAI Sector C | https://www.elverger.es/ajuntament/urbanisme/pai-sector-c-partida-barranquets/ | Operativa — memoria PAI + anexos PDF |
| Registro programas | https://www.elverger.es/ajuntament/urbanisme/registre-de-programes-i-agrupacions-dinteres-urbanistic/ | Operativa — certificado + registro PDF |
| Sede electrónica | https://elverger.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://elverger.sedelectronica.es/board | Operativa — tabla HTML preview-document (~10 filas) |
| Transparencia sede | https://elverger.sedelectronica.es/transparency/ | Operativa — sin sección urbanismo dedicada |
| Catálogo trámites | https://elverger.sedelectronica.es/dossier | Lento / timeout intermitente en CI |
| Visor UrbanImpacte | https://el-verger-atlas.urbanimpacte.com/ | Operativo — SPA sin API pública identificada |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia ICV) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento vigente | WordPress — PDFs en `/wp-content/uploads/` (memorias, planos TIF, edictos BOP/DOGv) |
| PAI / proyectos | Página dedicada PAI Sector C con anexos PDF |
| Instrumentos ICV | WFS GeoJSON zonificación (planes parciales, PGOU, homologaciones) |
| Tablón sede | HTML estático Wicket — ~10 anuncios recientes (agosto 2026: presupuesto, subvenciones, ordenanzas) |
| Licencias | Sin edictos de licencia en tablón reciente; trámites vía sede (requiere identificación) |

### Tablón sede (agosto 2026)

- Sin anuncios de licencias de obra ni planeamiento recientes
- Ordenanzas municipales (control tenencia gatos, condiciones estéticas, etc.)
- Subvenciones Generalitat

### WordPress planejament (2024–2026)

- PGOU: memoria, ordenanzas, planos clasificación/usos (TIF + PDF)
- Plan Parcial Sector D-3, Sector E, modificación residencial norte
- Edictos reparcelación, urbanización, aprobación definitiva PGOU
- PAI Sector C Partida Barranquets (marzo 2023)

## Cómo se publican licencias

- Edictos teóricamente en tablón sede (`preview-document/...`) — ninguno urbanístico en scrape actual
- Sin dataset histórico de concesiones con coordenadas
- Trámites vía sede / dossier (sin listado público de concesiones)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=03082` (~15 instrumentos únicos con polígonos)
  - Visor UrbanImpacte: `https://el-verger-atlas.urbanimpacte.com/` (SPA, sin endpoint ArcGIS/WFS público)
- **Estrategia:** escaneo paginado WFS GeoJSON; matching textual título↔`denominaci` (p. ej. «SECTOR D-3» → plan parcial ICV)
- **Limitaciones:**
  - Geometría ICV es zonificación PGOU/planes parciales, no parcela catastral ni licencia individual
  - Visor UrbanImpacte sin API scrapeable (Cloudflare SPA)
  - Tablón paginado Wicket (~10 filas visibles sin AJAX)
  - PDFs/planos TIF sin georreferenciación embebida

### Instrumentos ICV destacados (cod_ine_mun=03082)

| Expediente | Denominación |
|------------|--------------|
| 00000000 | Plan general |
| 19940417 | PLAN PARCIAL "POU DEL MORO-1" |
| 19930021 | PLAN PARCIAL DEL SECTOR S.U.P. RAFALS |
| 19940463 | PLAN PARCIAL "ERMITA II" |
| 19981338 | PLAN PARCIAL LA GUARDIA-3 |
| 2010 | PLAN PARCIAL DEL SECTOR CANSALADES-10 |
| 20011966 | HOMOLOGACIÓN Y PLAN PARCIAL SECTOR ADUANES-1 |
| 20060513 | Homo y PP del SUP Saladar 2 y UE Saladar 4 |
| 20011281 | HOMOLOGACIÓN Y PLAN PARCIAL U.E.UNICA SC.A SUNP CANSALADES-UMBRIA |

## Limitaciones generales

- Tablón: paginación Wicket AJAX (scrape estático ≈10 anuncios recientes)
- Sin API REST de expedientes urbanísticos públicos
- Escaneo ICV WFS completo ~2 min (28 páginas × 500 features); cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`El Verger`); manifest usa `Alicante`
- Sede con certificado SSL caducado (`insecure_ssl: true`)

## Adapter implementado

`municipio/adapters/el_verger.py` — WordPress seed pages + PDFs + tablón sede + ICV WFS partial.
