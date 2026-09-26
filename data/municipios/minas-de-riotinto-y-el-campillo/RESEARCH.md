# Minas de Riotinto y El Campillo — investigación portal ayuntamiento

**Municipio:** Minas de Riotinto y El Campillo (Huelva, Andalucía)  
**Slug:** `minas-de-riotinto-y-el-campillo`  
**BOJA:** `boja` (1 entrada en CSV)  
**Nota:** El ayuntamiento unificado corresponde a **Minas de Riotinto** (INE 21052); El Campillo es pedanía del término municipal.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (Saga Suite / Dip. Huelva) | https://www.aytoriotinto.es | Áreas temáticas, urbanismo, PGOU |
| Urbanismo | https://www.aytoriotinto.es/es/areas-tematicas/urbanismo/ | Sección temática urbanismo |
| PGOU | https://www.aytoriotinto.es/es/areas-tematicas/urbanismo/pgou/ | P.G.O.U (landing; sin PDFs enlazados actualmente) |
| Sede electrónica (espublico gestiona) | https://minasderiotinto.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://minasderiotinto.sedelectronica.es/board | Edictos HTML tabla (~10 visibles) |
| Catálogo trámites | https://minasderiotinto.sedelectronica.es/dossier | Categoría URBANISMO (Wicket; timeout frecuente en CI) |
| Transparencia | https://minasderiotinto.sedelectronica.es/transparency | Carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (17 docs, Wicket AJAX) |
| Normativa sede | https://minasderiotinto.sedelectronica.es/normative.21 | Normativa urbanística (carga lenta / vacía en CI) |

**Nota SSL:** `www.aytoriotinto.es` bloquea algunos clientes (WAF) o requiere `insecure_ssl` en CI; el adapter usa `insecure_ssl: true`.

## Cómo se listan expedientes / proyectos

1. **Saga Suite (OpenCMS):** páginas estáticas con enlaces a PDF en `/export/sites/riotinto/es/.galleries/...`. Sin API JSON ni listado de expedientes individuales. El PGOU no publica documentos descargables en la página actual.
2. **Tablón espublico:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Solo ~10 filas en primera página. Aparece «CONVENIO DE GESTION INTEGRAL - MINAS RIOTINTO» (jun 2026).
3. **Transparencia sede:** carpeta urbanismo con 17 documentos; requiere sesión Wicket AJAX para listar (no UUID estático en HTML inicial).
4. **SITUADIFUSION (Junta de Andalucía):** consulta regional de planeamiento para INE 21052; sin API REST pública de geometría por expediente.

## Cómo se publican licencias

- **No hay listado histórico público** de licencias concedidas en el portal municipal.
- El tablón sede publica mayoritariamente empleo, cobranza y subvenciones; sin licencias de obra visibles en la primera página.
- Trámites destacados en sede: «Solicitud de Certificado o Informe Urbanístico», categoría URBANISMO en dossier.
- El adapter devuelve páginas informativas del tablón y catálogo de trámites (patrón Lepe/Vera).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - No hay visor urbanístico municipal (ArcGIS, GeoJSON, WFS) enlazado desde el portal.
  - SITUADIFUSION Junta de Andalucía (`ws132.juntadeandalucia.es/situadifusion`) — consulta de planeamiento general, sin polígonos por expediente enlazables.
  - IDEAndalucía / catastro: sin capa WFS municipal de sectores con código de expediente.
  - PDF «Parques y Jardines» (urbanismo) sin georreferencia.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** solo PDFs sin georreferencia; tablón sin coordenadas; consulta de expedientes autenticada; PGOU sin documentos públicos en web.

## Limitaciones

- WAF en `www.aytoriotinto.es` desde algunas IPs (requiere `insecure_ssl` y User-Agent identificable).
- Tablón sede: paginación Wicket no scrapeada (solo primera página).
- Transparencia urbanismo: requiere AJAX Wicket para listar documentos.
- `/dossier` con timeout frecuente (>30s) en CI.
- Sin listado público de licencias históricas.
- PGOU landing vacío de PDFs (solo política de privacidad embebida).

## Referencias de patrón

- **Lepe** (`lepe.py`): espublico tablón + PDFs web (Drupal).
- **Vera** (`vera.py`): espublico tablón + ordenanzas web.
- **Bornos** (`bornos.py`): SITUADIFUSION referencia planeamiento.
