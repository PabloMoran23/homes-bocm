# Frigiliana — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `frigiliana` |
| Provincia | Málaga |
| CCAA | Andalucía |
| Boletín | BOJA (`boletin_source_id: boja`) |
| Web oficial | https://frigiliana.es |
| Sede electrónica | https://frigiliana.sedelectronica.es (espublico gestiona / eHome) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web WordPress (Divi) | https://frigiliana.es/urbanismo/ | PGOU/NNSS adaptadas LOUA: PDFs memoria, normativa, planos clasificación/usos/protección |
| PGOU y legislación | https://frigiliana.es/urbanismo-pgou-y-legislacion/ | Contexto normativo PGOU, BIC |
| Otros documentos | https://frigiliana.es/urbanismo-otros-documentos/ | Enlaces adicionales planeamiento |
| Formularios urbanismo | https://frigiliana.es/descarga-de-formularios-2/ | Modelos licencia obra, licencia urbanística, apertura, etc. (sin listado de concesiones) |
| Trámites urbanismo | https://frigiliana.es/urbanismo-ejecucion-obra/ | Página informativa licencias de obra |
| Tablón sede | https://frigiliana.sedelectronica.es/board | Tabla HTML espublico: expediente, procedimiento, categoría, descripción, fecha, preview PDF |
| Catálogo trámites | https://frigiliana.sedelectronica.es/dossier | Trámites sede (licencias vía presentación electrónica) |
| Transparencia sede | https://frigiliana.sedelectronica.es/transparency | Portal transparencia espublico (sin sección urbanismo dedicada) |
| Consulta expedientes | https://frigiliana.sedelectronica.es/expedientes | Requiere identificación; no hay listado público |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta regional PGOU/NNSS (sin API por expediente municipal) |

## Cómo se listan expedientes / proyectos

- **Tablón espublico:** HTML estático con filas `<tr>` y celdas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlace a `/preview-document/{uuid}`. Procedimientos urbanísticos aparecen como «Planeamiento de Desarrollo», «Licencias de Ocupación», etc.
- **Web municipal:** WordPress con enlaces directos a PDFs en `/wp-content/uploads/` (planeamiento vigente y adaptado, BOJA BIC 2015).
- **No hay** visor de expedientes público ni API JSON embebida.

## Cómo se publican licencias

- **Tablón:** edictos y anuncios de licencias de ocupación vía dominio público (no licencias de obra individuales con coords).
- **Formularios:** solo modelos PDF para solicitud (licencia de obras, licencia urbanística, apertura) — no registro histórico.
- **Sede:** trámites electrónicos en `/dossier`; consulta de expedientes autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** PGOU publicado como PDF raster en web municipal; SITUA/VITUA Junta de Andalucía tiene planeamiento general del municipio pero **sin enlace** expediente↔polígono en portal municipal. No hay visor ArcGIS/WFS municipal ni campo de código de expediente en capa GIS pública.
- **Estrategia:** adapter documenta filas de metadatos (PDFs planeamiento + tablón + SITUA); el orquestador aplica centroide municipal + jitter vía `geocode`.
- **Limitaciones:** planos solo PDF sin georreferencia; tablón sin coordenadas; consulta expedientes requiere login; SITUA no expone query por `1420/2024` u otro código del tablón.

## Limitaciones generales

- Tablón actual (sep 2026) mayoritariamente contratación/padrón; proyectos urbanísticos históricos en BOJA/BOCM ya parseados.
- SSL sede espublico: certificado válido; no requiere `insecure_ssl`.
- Sin paginación en tablón (pocas filas visibles).
