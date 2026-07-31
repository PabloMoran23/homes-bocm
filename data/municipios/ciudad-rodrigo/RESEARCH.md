# Ciudad Rodrigo — investigación portal ayuntamiento

**Fecha:** 2026-07-22  
**Slug:** `ciudad-rodrigo`  
**BOCYL regional (referencia):** 17 filas

## Resumen

Ciudad Rodrigo publica planeamiento y autorizaciones urbanísticas en **dos portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.ciudadrodrigo.es/ayuntamiento | WordPress | PGOU, estudios de detalle, modificaciones PGOU, autorizaciones uso excepcional |
| Sede electrónica | https://ciudadrodrigo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, transparencia, consulta expedientes (auth) |

## Fuentes de proyectos / expedientes

### 1. WordPress REST — normativa urbanística

Categorías WP (REST `wp-json/wp/v2/posts`):

| ID | Categoría | Posts (~) |
|----|-----------|-----------|
| 152 | Normativa urbanística de aplicación — PLANEAMIENTO | 32 |
| 154 | Normativa urbanística en tramitación — PLANEAMIENTO | 5 |
| 151 | Urbanismo — Autorizaciones de uso excepcional | 77 |
| 153 | Normativa urbanística de aplicación — GESTIÓN | 8 |

**API:** `https://www.ciudadrodrigo.es/ayuntamiento/wp-json/wp/v2/posts?categories={id}&per_page=100`

Contenido: modificaciones PGOU, estudios de detalle, proyectos de actuación (sectores/UE), autorizaciones uso excepcional en suelo rústico. Algunos posts enlazan PDFs en `wp-content/uploads/urbanismo/`.

### 2. PGOU — documentación estática

- **URL:** https://www.ciudadrodrigo.es/ayuntamiento/plan-general-de-ordenacion-urbana-municipal/
- PDFs de normativa, planos y ordenación detallada por sectores (24.1, 24.2, SU-C, etc.)
- Aprobación definitiva PGOU: BOCYL 8/01/2010

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://ciudadrodrigo.sedelectronica.es/board/
- **Formato:** tabla HTML espublico con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación
- **Paginación:** ~10 filas visibles; histórico limitado en vista pública
- **SSL:** certificado con cadena incompleta en algunos entornos → `insecure_ssl: true`

### 4. Transparencia / expedientes

- Transparencia: https://ciudadrodrigo.sedelectronica.es/transparency/ (documentación general)
- Expedientes: https://ciudadrodrigo.sedelectronica.es/expedientes — requiere identificación; sin listado público

## Fuentes de licencias

1. **WP categoría 151** — autorizaciones de uso excepcional (construcción, instalaciones, etc.)
2. **Tablón sede** — anuncios puntuales de licencias/obras cuando se publican
3. **Trámites impresos:** https://www.ciudadrodrigo.es/ayuntamiento/tramites-y-gestiones-impresos/
   - Solicitud de Licencia Urbanística de Obras
   - Declaración responsable obras menores
   - Licencia segregación/parcelación, 1ª ocupación, etc.

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Web ayuntamiento: PGOU y estudios de detalle solo en PDF/planos estáticos
  - Junta de Castilla y León IDE: sin capa WFS/ArcGIS pública enlazable por código de expediente para Ciudad Rodrigo
  - Sede espublico: sin visor SIG integrado
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [40.5986, -6.5333]`)
- **Limitaciones:** delimitación de ámbitos solo en planos PDF sin georreferencia descargable; consulta de expedientes requiere login

## Limitaciones

- Tablón sede muestra ventana corta (~10 anuncios recientes); histórico completo no indexable sin autenticación
- Licencias sin geolocalización en fuentes públicas
- Certificado SSL sede puede requerir `insecure_ssl`
- Sin API REST de expedientes urbanísticos estructurados

## Estrategia adapter

1. **proyectos.jsonl:** REST API categorías 152/154/151/153 + PDFs PGOU + tablón sede (filtro urbanismo)
2. **licencias.jsonl:** posts WP autorizaciones uso excepcional + PDFs trámites + tablón + páginas informativas sede
