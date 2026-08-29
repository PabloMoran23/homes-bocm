# Jabugo — investigación portal ayuntamiento

**Municipio:** Jabugo (Huelva, Andalucía)  
**Slug:** `jabugo`  
**INE:** 21042  
**BOJA:** `boja` (2 entradas en CSV)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress) | https://jabugo.es | Portal turístico/municipal (Elementor) |
| Área infraestructura/urbanismo | https://jabugo.es/area-de-infraestructura/ | Delegación de Infraestructuras, Urbanismo y Servicios Generales (sin PDFs) |
| Sede electrónica (espublico) | https://jabugo.sedelectronica.es | Tablón, transparencia, trámites |
| Tablón de anuncios | https://jabugo.sedelectronica.es/board/ | 10 anuncios visibles (cobranza, padrón, piscina…) |
| Transparencia | https://jabugo.sedelectronica.es/transparency | Carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (97 docs) |
| Trámites urbanísticos | https://jabugo.sedelectronica.es/citizen-service/ff09163c-e59b-43c0-9540-e35e4a26c4c4 | DR obras, licencia urb., actividades, terrazas |
| SITUADIFusión (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta PGOU aprobado (CP-045/2022) |

**Nota:** la API REST de WordPress (`/wp-json/`) devuelve 403 en CI; el contenido urbanístico no está publicado como PDFs en la web.

## Cómo se listan expedientes / proyectos

1. **Transparencia sede:** índice con carpeta urbanismo (97 documentos). El listado interno requiere navegación Wicket AJAX (no hay UUID estático en HTML inicial ni en resultados de búsqueda web).
2. **Tablón sede:** tabla HTML espublico (`class_name`, `class_folderCode`, `class_folderName`, …). Solo primera página (~10 filas); sin anuncios urbanísticos en el momento de la investigación.
3. **PGOU CP-045/2022:** aprobación definitiva parcial (julio 2023) y subsanación/inscripción (noviembre 2023) publicadas en BOJA; el propio BOJA indica publicidad en sede electrónica del ayuntamiento.
4. **SITUADIFusión:** visor regional de planeamiento aprobado (metadatos, sin polígonos por expediente enlazables).

## Cómo se publican licencias

- **No hay listado histórico público** de licencias concedidas.
- Trámites telemáticos vía sede (`citizen-service`, `/dossier`) requieren identificación.
- El adapter devuelve páginas informativas del tablón y catálogo de trámites urbanísticos (patrón Lepe/Cártama).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - Sin visor urbanístico municipal (ArcGIS, GeoJSON, WFS) en jabugo.es ni sede.
  - SITUADIFusión: metadatos del PGOU, sin API REST de geometría por expediente.
  - IDEAndalucía / SIU: sin capa WFS municipal enlazable por código de expediente para Jabugo.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** solo PDFs/documentos sin georreferencia; transparencia urbanismo con 97 docs no listables sin sesión Wicket completa.

## Limitaciones

- WordPress REST API bloqueada (403).
- Tablón sede: solo primera página scrapeada.
- Transparencia urbanismo: 97 documentos tras carpeta Wicket AJAX (no UUID público descubierto).
- Sin listado público de licencias históricas.

## Referencias de patrón

- **Lepe** (`lepe.py`): Huelva, espublico + sin GIS.
- **Cártama** (`cartama.py`): espublico tablón + transparencia + seeds PGOU.
