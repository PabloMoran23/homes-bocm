# El Escorial — investigación portal ayuntamiento

**Municipio:** El Escorial (La Leal Villa de El Escorial)  
**Comunidad:** Comunidad de Madrid  
**INE municipio / SITCM:** `054` (`CD_MUNICIPIO`)  
**Fecha investigación:** 2026-08-03

**Nota:** El Escorial y **San Lorenzo de El Escorial** son municipios distintos (sede, dominio y plataforma diferentes).

## Resumen

El ayuntamiento publica planeamiento y documentación urbanística en la **web corporativa WordPress + Elementor** (`elescorial.es`), principalmente en el portal de transparencia integrado (`pt-urbanismo-y-medio-ambiente`). Trámites y tablón de anuncios están en la **sede electrónica espublico gestiona** (`elescorial.sedelectronica.es`, Apache Wicket/YUI). No hay dataset abierto municipal de licencias concedidas ni visor urbanístico propio; geometría de ámbitos de planeamiento vía **SITCM / WFS Comunidad de Madrid**.

## URLs base

| Recurso | URL | Tecnología |
|---------|-----|------------|
| Web corporativa | https://elescorial.es | WordPress 6.x, tema Hello Elementor, Elementor Pro, Rank Math |
| Urbanismo (citizen) | https://elescorial.es/urbanismo-y-vivienda/ | WP Elementor — formularios PDF licencias/ordenanzas |
| Portal transparencia | https://elescorial.es/portal-de-transparencia/ | WP |
| PT Urbanismo y Medio Ambiente | https://elescorial.es/pt-urbanismo-y-medio-ambiente/ | WP — NNSS, planes parciales, medio ambiente (~170 PDFs) |
| Formularios | https://elescorial.es/formularios/ | WP tabla HTML — modelos licencia/actividades |
| Bandos municipales | https://elescorial.es/bandos/ | WP — bandos (no tablón licencias) |
| Portal Suelo 4.0 CCAA | https://www.comunidad.madrid/inversion/inicia-desarrolla-tu-empresa/portal-suelo-40 | Externo CCAA |
| Sede electrónica | https://elescorial.sedelectronica.es | **espublico gestiona** (meta author), Wicket, nginx |
| Sede inicio | https://elescorial.sedelectronica.es/info | Redirect desde `/` |
| Tablón de anuncios | https://elescorial.sedelectronica.es/board | HTML tabla espublico |
| Catálogo trámites | https://elescorial.sedelectronica.es/dossier → `dossier.0` | Lista `catalog/t/{uuid}` (requiere cookies/redirect) |
| Consulta expedientes | https://elescorial.sedelectronica.es/expedientes | **Certificado digital** (carpeta ciudadano) |
| Transparencia sede | https://elescorial.sedelectronica.es/transparency | Índice legal/administrativo (sin dossier urbanismo) |
| Validación documentos | https://elescorial.sedelectronica.es/document-validation | |
| Portal tributario | https://tributos.elescorial.es | Tasas urbanísticas / ICIO |
| Visor SITCM (CCAA) | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=054 | Enlace en home `elescorial.es` |
| WFS SITCM | https://idem.comunidad.madrid/geoserver3/ows | GeoServer 3 |

### Dominios legacy / no operativos

| URL referenciada en web | Estado |
|-------------------------|--------|
| https://sede.elescorial.es/GDCarpetaCiudadano/… | **DNS no resuelve** (enlace perfil contratante en menú WP) |
| datos.gob.es (publisher El Escorial) | **0 conjuntos de datos** publicados |

## CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web `elescorial.es` | WordPress + Elementor + Ultimate Elementor; REST `wp-json/wp/v2/` disponible |
| Sede `*.sedelectronica.es` | espublico gestiona: Java Wicket, YUI 2, Apache Wicket AJAX, JSESSIONID cookies |
| Tablón | Tabla `AdvertisementBoardListPanel` con `data-label` en `<td>` |
| Documentos tablón | `preview-document/{uuid}` → iframe `/preview/pdf/{token}.pdf` |
| Trámites | Páginas `catalog/t/{uuid}` con formulario Wicket informativo |
| GIS municipal | No propio; SITCM CCAA |

## Planeamiento / expedientes urbanísticos

### Dónde se listan

1. **PT Urbanismo y Medio Ambiente** (`pt-urbanismo-y-medio-ambiente/`)
   - **Planeamiento general:** NNSS (memorias, normas, planos por capítulo), catálogo bienes protegidos, modificaciones puntuales históricas (PDFs en `wp-content/uploads/2023/07/` y `2023/05/`).
   - **Planeamiento de desarrollo:** Planes parciales y PERI documentados (Los Escoriales 1967, El Tomillar 1996, Sector 1 Ensanche, Montencinar/PERI-3, PERI-1 Peralejo, etc.; PDFs 2023/07 y 2025/02).
   - **Medio ambiente:** estudios acústicos, planes protección civil, línea verde, etc.
   - Estructura: encabezados `<h2>` + enlaces `<a href="…pdf">` (sin acordeones Visual Composer; ~170 PDFs).

2. **Urbanismo y vivienda** (`urbanismo-y-vivienda/`)
   - Enlaces a PDFs de licencias, ordenanzas y modificaciones NNSS puntuales (2023/06).
   - No listado de expedientes en tramitación.

3. **Tablón sede** (`/board`)
   - Columnas: Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha de Publicación.
   - Clases CSS: `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
   - Expedientes urbanísticos aparecen cuando se publican edictos (información pública, aprobaciones); jul 2026: tablón mayoritariamente administrativo (subvenciones, empleo, JGL).

4. **Consulta expedientes sede** (`/expedientes`)
   - Solo interesados con certificado; no scrapeable públicamente.

5. **BOCM**
   - Fuente complementaria regional (`bocm_count`: 11 en queue); no sustituye listado municipal estructurado.

### No existe

- API JSON de expedientes urbanísticos.
- Visor ArcGIS municipal.
- Dataset datos.gob.es de planeamiento (San Lorenzo sí publica; El Escorial no).

## Licencias de obra

### Publicación de concesiones

- **No hay** dataset histórico ni GeoJSON municipal de licencias concedidas.
- Concesiones / notificaciones / edictos de licencia se publican en el **tablón electrónico** cuando el ayuntamiento los anuncia.
- Jul 2026: sin entradas claras de licencia de obra en tablón (10 anuncios recientes; mayoría otras materias).

### Modelos y trámites (no concesiones)

| Fuente | Contenido |
|--------|-----------|
| `urbanismo-y-vivienda/` | PDFs: obra menor, primera ocupación, comunicación previa, declaración responsable, LICENCIAS_URBANISTICAS.pdf, modificaciones NNSS |
| `formularios/` | Tabla WP: 8 trámites URBANISMO Y VIVIENDA (+ terrazas en comercio) |
| Sede `dossier.0` | 21 trámites urbanísticos en `catalog/t/{uuid}` (solicitud, no listado de resoluciones) |

### Trámites urbanísticos en sede (catálogo)

UUIDs útiles para el adapter (título → `catalog/t/…`):

| Trámite | UUID |
|---------|------|
| Licencia Urbanística Obra Mayor | `240d21a3-dd43-41e0-841f-bb6d09d2beec` |
| Licencia Obra Menor. Reformas | `07cfadb3-1e36-4ca3-ae45-eae60a79e36d` |
| Licencia Primera Ocupación | `d76f3a28-6398-4f3f-92bd-8e9ede582a86` |
| Licencia Segregación Parcelaria | `6867c0aa-092c-4f5b-b7f8-00415cafc8a9` |
| Licencia Agrupación Parcelaria | `7784285c-b9a7-4f94-b1e7-0e8354cf10f7` |
| Licencia Alineación Oficial Obra | `5daba3d9-d7fb-451c-9f96-a4d071874123` |
| Licencia Paneles Solares | `b72a13ef-5cc3-40cb-9354-a2b56cf12f76` |
| Licencia Acometida | `10c2f03c-bda7-4a05-a814-4b0691c99593` |
| Licencia Actividades e Instalaciones | `8ea855f3-7d86-4b65-8033-010ae7d38ebb` |
| Declaración Responsable Actividades | `4f46a25f-5318-40d7-bcaf-76fa49e66be3` |
| Modificación Puntual Planeamiento | `ae9afad4-e921-457f-998d-854ec5a135e5` |
| Actuación Urbanística | `aa085ae3-05de-4047-9fbc-9a1c8478e984` |
| Calificación / Certificado / Informe Urbanístico | varios UUID en dossier |

## GIS / geometría

**geometry_status:** `partial`

### Visor web

```
https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=054
```

### WFS principal (ámbitos de planeamiento)

```
GET https://idem.comunidad.madrid/geoserver3/ows
  ?service=WFS
  &version=1.0.0
  &request=GetFeature
  &typeName=sitcm:VPLA_V_AMBITO
  &CQL_FILTER=DS_MUNICIPIO='EL ESCORIAL'
  &outputFormat=application/json
  &srsName=EPSG:4326
```

| Campo | Uso en adapter |
|-------|----------------|
| `DS_MUNICIPIO` | `EL ESCORIAL` |
| `CD_MUNICIPIO` | `054` |
| `DS_NOMB_AMB` | Nombre/código ámbito (enlace textual con PDFs) |
| `CD_UNI` | ID único ámbito (ej. `PG_54_1996_AMB_0000002`) |
| `DS_FIG_DES` | Plan Parcial, Estudio Detalle, Plan Especial Reforma Interior, … |
| `DS_CLAS_SUE`, `DS_US_PRED`, `NM_AREA`, `FC_BOCM`, `DS_DOCU` | Metadatos proyecto |
| `geometry` | Polígono ámbito (EPSG:25830 nativo; pedir 4326 con `srsName`) |

**44 features / 32 ámbitos únicos** (jul 2026), ejemplos: `JUAN DE AUSTRIA`, `PERI-3 MONTENCINAR`, `S-2 TOMILLAR`, `UA-10 RENFE`, `PERI-1 PERALEJO`, …

### Capas WFS adicionales (SITCM)

Útiles para enriquecer planeamiento si hace falta geometría de clasificación/ordenanzas:

- `sitcm:VPLA_V_AMBITO_LIMITE_SQL` — límites ámbitos
- `sitcm:VPLA_V_CLASIFICACION` / `sitcm:VPLA_V_ORDENANZA` — clasificación y ordenanzas PG
- `sitcm:VPLA_V_AMBITO_MODIF` — modificaciones ámbitos

No hay capa WFS de licencias de obra ni expedientes individuales.

### Enlace expediente ↔ geometría

- Tablón y PDFs **no** enlazan `CD_UNI` ni objectId GIS.
- Estrategia: matching heurístico por código/nombre en título (`PERI-3`, `MONTENCINAR`, `TOMILLAR`, `UA-`, etc.) contra `DS_NOMB_AMB`.

## Cómo scrapear (estrategia adapter)

Patrón recomendado: híbrido **El Molar** + **Villavieja del Lozoya** + **Hoyo de Manzanares**.

### 1. Proyectos / planeamiento

1. Crawl semillas WP:
   - `pt-urbanismo-y-medio-ambiente/`
   - `urbanismo-y-vivienda/` (modificaciones NNSS)
   - `ordenanzas-2/` / `reglamentos-2/` si procede
2. Extraer todos `href="…wp-content/uploads/….pdf"` con título del `<a>` o contexto de `<h2>`.
3. Inferir tipo: NNSS, plan parcial, PERI, modificación puntual, estudio ambiental, ordenanza.
4. Fecha: regex en URL (`/2023/07/`), nombre archivo (`BOCM-YYYYMMDD`), año en título.
5. Semillas WFS: ingestar 32 ámbitos como proyectos con `geom_geojson`; `CD_UNI` como clave estable.

### 2. Licencias (concesiones)

1. **Tablón** `GET /board` — parsear `<tr>` con `preview-document`:
   ```python
   RE_BOARD_CELL = r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>'
   RE_PREVIEW = r'preview-document/([a-f0-9-]+)'
   ```
2. Resolver PDF: fetch `preview-document/{uuid}` → extraer `src="/preview/pdf/….pdf"` del iframe.
3. Filtrar licencias con regex (`licencia`, `obra`, `declaración responsable`, `comunicación previa`, `notificación`, `edicto`, `primera ocupación`).
4. Usar columna **Expediente** (`class_folderCode`) como `expediente_codigo` cuando exista (formato `NNNN/YYYY`).
5. **No confiar** en búsqueda GET `?description=` del tablón (devuelve siempre ~10 filas sin filtrar). Búsqueda Wicket POST opcional y frágil.

### 3. Licencias (modelos / trámites informativos)

1. PDFs en `urbanismo-y-vivienda/` y filas `URBANISMO Y VIVIENDA` en `formularios/`.
2. Catálogo sede: `GET /dossier` con **CookieJar** (redirect a `dossier.0`); regex:
   ```python
   r'href="(https://elescorial\.sedelectronica\.es/catalog/t/[a-f0-9-]+)"[^>]*>([^<]+)</a>'
   ```
3. Tratar como filas informativas (`min_rows: 0` para concesiones reales es aceptable).

### 4. Cliente HTTP

- `User-Agent` identificable, `request_delay_s` ~0.35.
- Sede: mantener `JSESSIONID` (CookieJar) para dossier y preview-document.
- `dossier` sin cookies → bucle redirect 302.

### 5. IDs estables

```
el-escorial-proy-{sha256(url|CD_UNI)[:14]}
el-escorial-lic-{sha256(preview_uuid|expediente)[:14]}
```

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| Tablón solo ~10 anuncios recientes, sin paginación visible | Histórico licencias incompleto vía tablón |
| Sin dataset licencias con coordenadas | Geometría licencias solo indirecta (BOCM / manual) |
| `/expedientes` requiere certificado | No consulta pública masiva |
| `sede.elescorial.es` caído | Ignorar enlaces WP a eAdmin legacy |
| Sin datos.gob.es El Escorial | Sin CSV/API alternativa planeamiento |
| WFS = ámbitos planeamiento, no parcelas licencia | `geometry_status: partial` |
| Transparencia sede sin dossier urbanismo UUID | No usar patrón Hoyo `transparency/{uuid}/` sin descubrir UUIDs |
| `dossier` lento / intermitente | Timeout 45–60s, reintentos |

## Municipios de referencia (mismo patrón)

| Municipio | Similitud |
|-----------|-----------|
| El Molar | espublico `board` + `dossier` + WFS SITCM + WP formularios |
| Villavieja del Lozoya | WP planeamiento PDFs + tablón espublico + WFS |
| Hoyo de Manzanares | WP urbanismo + tablón + transparencia dossier (El Escorial no tiene UUID urbanismo en sede) |
| San Lorenzo de El Escorial | **Distinto:** eAdmin add4u + WP `aytosanlorenzo.es` — no reutilizar adapter |

## Fuentes consultadas

- https://elescorial.es/
- https://elescorial.es/pt-urbanismo-y-medio-ambiente/
- https://elescorial.es/urbanismo-y-vivienda/
- https://elescorial.es/formularios/
- https://elescorial.sedelectronica.es/board
- https://elescorial.sedelectronica.es/dossier.0
- https://idem.comunidad.madrid/geoserver3/ows (WFS `sitcm:VPLA_V_AMBITO`)
- https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=054
- https://datos.gob.es/es/catalogo?publisher_display_name=El+Escorial
