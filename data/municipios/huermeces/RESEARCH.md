# Huérmeces — investigación portal ayuntamiento

**Municipio:** Huérmeces (provincia Burgos, Castilla y León)  
**Fecha:** 2026-09-19  
**BOCYL (referencia):** 1 aviso  
**INE:** 09140 | **PLAU:** provincia=9, municipio=140

## Resumen

Huérmeces dispone de **web corporativa Drupal 10** (tema Toools, red Diputación de Burgos) y **sede electrónica espublico gestiona**. El planeamiento urbanístico está centralizado en **PlanPublica / SiuCyL** (JCyL): el municipio figura como **«sin planeamiento general»** (SPG). No hay planes parciales ni sectores en IDECyL WFS. El tablón municipal publica bandos de obras y requerimientos en el conjunto histórico, pero no concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.huermeces.es/inicio | Drupal Toools |
| Sede electrónica | https://huermeces.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://huermeces.sedelectronica.es/board | 7 avisos (sep 2026); bandos de obras |
| Catálogo de trámites | https://huermeces.sedelectronica.es/dossier | Requiere cookie de sesión (warm-up vía `/board`); ~106 trámites |
| Transparencia | https://huermeces.sedelectronica.es/transparency | |
| Normativa | https://www.huermeces.es/normativa | Sin PDFs de urbanismo indexados |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=9&municipio=140 | 1 fila: «SIN PLANEAMIENTO GENERAL» (SPG) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=9&municipio=140 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=09140 | Mapa interactivo regional |
| OVC Diputación Burgos | https://ovc.diputaciondeburgos.es/ | Contratación provincial |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **SPG** — «SIN PLANEAMIENTO GENERAL» (sin PGOU/PGOM aprobado en JCyL).
- No hay planes parciales, sectores ni estudios de detalle publicados en PlanPublica.

### Tablón de anuncios — cómo se listan

HTML con tabla Wicket (`<tbody>`). Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Enlaces PDF vía `preview-document/{uuid}`.

**Avisos urbanismo-relevantes (sep 2026):**

| Título | Procedimiento | Categoría |
|--------|---------------|-----------|
| REQUERIMIENTO DE DOCUMENTACIÓN PARA OBRAS EN EL CONJUNTO HISTÓRICO DE HUÉRMECES | Certificados o Informes | Bandos |
| Bando: Obras | Certificados o Informes | Bandos |
| Limpieza de solares | Certificados o Informes | Bandos |

### Catálogo de trámites (dossier)

Listado HTML con enlaces `/catalog/t/{uuid}`. Trámites urbanísticos identificados:

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Licencia de Ocupación
- Modificación del Planeamiento de Desarrollo
- Planeamiento General (Modificación)
- Solicitud de Actuación Urbanística
- Solicitud de Certificado o Informe Urbanístico
- Solicitud de Declaración de Ruina

Son páginas informativas de trámite; no publican concesiones con coordenadas.

### Licencias de obra

No hay dataset ni tablón de concesiones georreferenciadas. Solo trámites informativos en dossier y bandos genéricos de obras.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Huérmeces'` → 1 `MultiPolygon` (ámbito municipal sin PG vigente)
  - SiUR JCyL: https://idecyl.jcyl.es/siur/index.html?id=09140
  - Capas `plau_cyl_sectores` y `plau_cyl_planes_parciales`: 0 features
- **Estrategia:** consulta WFS por municipio; enriquecer filas PLAU/WFS con `geom_geojson`; intentar match por código de sector en títulos del tablón (poco probable sin sectores)
- **Limitaciones:** sin visor municipal propio; sin geometría por expediente/licencia individual; licencias solo informativas

## 3. Estrategia de ingesta (adapter)

| Fuente | Método | Salida |
|--------|--------|--------|
| PLAU JCyL | Scrape HTML tabla PlanPublica | `proyectos.jsonl` |
| IDECyL WFS | GetFeature GeoJSON EPSG:4326 | `proyectos.jsonl` + geometría |
| Tablón sede | Parse tabla Wicket | `proyectos.jsonl`, `licencias.jsonl` |
| Dossier trámites | Parse catálogo (tras warm-up cookie) | `licencias.jsonl`, `proyectos.jsonl` (informativos) |

## 4. Limitaciones

- Dossier requiere visita previa a `/board` para cookies de sesión (~15 s).
- Sin licencias publicadas con fecha de concesión ni coordenadas.
- Municipio sin planeamiento general aprobado: geometría WFS es contorno municipal genérico, no ámbitos de proyecto.
