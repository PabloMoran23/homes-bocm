# Lepe — investigación portal ayuntamiento

**Municipio:** Lepe (Huelva, Andalucía)  
**Slug:** `lepe`  
**BOCM/BOJA:** `boja` (5 entradas en CSV)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Drupal 7) | https://ayuntamiento.lepe.es | Área de Urbanismo, PDFs de planeamiento |
| Urbanismo | https://ayuntamiento.lepe.es/es/urbanismo | Índice temático urbanismo |
| Planeamiento en trámite | https://ayuntamiento.lepe.es/es/node/4175 | Landing (sin listado dinámico) |
| Planeamiento desarrollo | https://ayuntamiento.lepe.es/es/node/455 | Enlaces a sectores y planes |
| Suelo urbanizable | https://ayuntamiento.lepe.es/es/node/454 | PDFs sectores (Avda Andalucía, etc.) |
| Suelo urbano no consolidado | https://ayuntamiento.lepe.es/es/node/870 | PDFs unidades de ejecución |
| PGOU | https://ayuntamiento.lepe.es/es/node/660 | Memoria, normas, planimetría |
| Sector Avda Andalucía Norte | https://ayuntamiento.lepe.es/es/node/13647 | Acuerdos aprobación/reparcelación |
| Plan especial temporeros | https://ayuntamiento.lepe.es/es/node/6625 | PDF plan especial |
| Sede electrónica (espublico) | https://lepe.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://lepe.sedelectronica.es/board/ | Edictos HTML tabla (10 visibles) |
| Transparencia | https://lepe.sedelectronica.es/transparency/ | Carpeta «7. URBANISMO…» (29 docs, Wicket AJAX) |

**Nota SSL:** `ayuntamiento.lepe.es` presenta certificado inválido en CI; el adapter usa `insecure_ssl: true`.

## Cómo se listan expedientes / proyectos

1. **Drupal:** páginas estáticas con enlaces directos a PDF en `/sites/ayuntamiento.lepe.es/files/*.pdf`. Sin API JSON ni listado de expedientes individuales. Los títulos se extraen del nombre de archivo.
2. **Tablón espublico:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Solo ~10 filas en primera página (paginación Wicket no implementada).
3. **Transparencia sede:** carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 29 documentos; requiere sesión Wicket AJAX para listar (no UUID estático en HTML inicial).

## Cómo se publican licencias

- **No hay listado histórico público** de licencias concedidas en el portal municipal.
- El tablón sede publica ocasionalmente edictos de urbanismo/actuaciones; la mayoría de filas visibles son empleo/presupuesto.
- Trámites de licencia vía sede (`/dossier`, `/expedientes`) requieren identificación.
- El adapter devuelve páginas informativas del tablón y catálogo de trámites (patrón Cártama/Alhaurín).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - No hay visor urbanístico municipal (ArcGIS, GeoJSON, WFS) enlazado desde el portal.
  - `agendaurbana.lepe.es` es portal de Agenda Urbana/EDUSI (proyectos europeos), sin capas GIS de expedientes.
  - Junta de Andalucía / IDEAndalucía: sin capa WFS municipal de sectores enlazable por código de expediente.
  - SIU (Ministerio Vivienda) tiene planeamiento a escala municipal pero sin polígonos por expediente.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** solo PDFs sin georreferencia; tablón sin coordenadas; consulta de expedientes autenticada.

## Limitaciones

- Certificado SSL inválido en web Drupal.
- Tablón sede: paginación Wicket no scrapeada (solo primera página).
- Transparencia urbanismo: requiere AJAX Wicket para listar documentos.
- Sin listado público de licencias históricas.
- `node/4175` (planeamiento en trámite) es landing vacío sin listado automático.

## Referencias de patrón

- **Cártama** (`cartama.py`): espublico tablón + transparencia.
- **Alhaurín el Grande** (`alhaurin_el_grande.py`): espublico + PDFs web.
- **Mijas** (`mijas.py`): WordPress + espublico con seed pages.
