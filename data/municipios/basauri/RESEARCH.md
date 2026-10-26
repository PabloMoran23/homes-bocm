# Basauri — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `basauri` |
| Web corporativa | https://www.basauri.eus (Drupal 10, ES/EU) |
| Sede electrónica | https://sede.basauri.eus (Joomla + Quix) |
| Carpeta STA / tablón | https://karpeta.basauri.eus/sta/… (`PAGE_CODE=BAS_TABLON`) |
| Provincia / CCAA | Bizkaia / Euskadi |

## Fuentes — planeamiento y expedientes

### Gestión urbanística (Drupal)

- Índice: https://www.basauri.eus/es/gestion-urbanistica
- PGOU: https://www.basauri.eus/es/pgou y https://www.basauri.eus/es/pagina/plan-general-de-ordenacion-urbana-de-basauri-pgou
- Planeamiento de desarrollo (listado extenso de PDFs PEOU, planos, estudios): https://www.basauri.eus/es/pagina/planeamiento-de-desarrollo-urbanistico
- Modificaciones urbanísticas: https://www.basauri.eus/es/pagina/modificaciones-urbanisticas
- Convenios urbanísticos (nodos `/es/convenio/...`): https://www.basauri.eus/es/gestion-urbanistica/convenios-urbanisticos

**Formato:** HTML Drupal con enlaces a PDFs en `/sites/basauri/files/YYYY-MM/...` y páginas de convenio con título `<h1>` y fechas en cuerpo. No hay JSON:API público ni listado RSS de expedientes.

### Transparencia

- Indicadores urbanismo (PGOU, convenios, planeamiento): rutas bajo `/es/indicador-de-transparencia/41*` enlazadas desde transparencia.

## Fuentes — licencias

### Catálogo de trámites (sede)

- Iframe embebido en https://sede.basauri.eus/es/tramites/tramites-por-secciones
- URL directa del catálogo: https://sede.basauri.eus/sede/index.php?catalogo=1&idioma=es
- Trámites L-* y C-* de obras/licencias/comunicaciones previas (temfa=63), p. ej. «L-5 Licencia para obras de edificación».

**Nota:** son páginas informativas de trámite; no publican concesiones con dirección/coordenadas.

### Tablón de anuncios (STA)

- Enlace desde sede: `karpeta.basauri.eus` → `CarpetaPublic` + `PAGE_CODE=BAS_TABLON`
- Patrón esperado: metadata JavaScript `metadata_TABLON…` (similar a otros STA CATSERV), con filas fecha / descripción / enlace.

**Limitación:** desde el entorno del agente la conexión TLS a `karpeta.basauri.eus` hace timeout (>25 s). El adapter intenta el tablón con `karpeta_insecure_ssl: true`; en local/CI puede completar filas de edictos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Cartografía municipal (PDF callejero, bases ETRS89 en Dropbox): https://www.basauri.eus/es/pagina/cartografia-digital-y-sistema-de-informacion-geografica — sin API ni enlace a expediente.
  - Mapa municipal / callejero: https://www.basauri.eus/es/mapa-municipal-callejero — sin capa REST pública identificada en HTML.
  - Diputación Foral de Bizkaia — ArcGIS REST `PX_Bilbao_Metropolitano_inf` (capas 119–122, 134): consulta por token en `ETIQUETA`/`DESCRIPCION` (`returnGeometry=true`, `outSR=4326`, `f=geojson`). No hay campo municipio=Basauri fiable; en pruebas no hubo coincidencias para títulos locales (Uriarte, AA-08, etc.).
- **Estrategia en adapter:** tras metadatos del proyecto, búsqueda opcional en capas ArcGIS metropolitanas; si no hay hit, geocode usará centroide manifest + jitter.
- **Limitaciones:** sin visor urbanístico municipal con código de expediente; tablón STA inaccesible desde cloud; planeamiento solo PDF.

## Limitaciones generales

- Sin dataset abierto de licencias concedidas.
- Drupal sin API pública de nodos.
- `karpeta.basauri.eus` puede bloquear o tardar en TLS desde redes externas.
- Paginación no aplicable (listados estáticos en páginas semilla).

## Semillas implementadas

Ver `DEFAULT_SEEDS` en `municipio/adapters/basauri.py` y `portal.config` en `manifest.yaml`.
