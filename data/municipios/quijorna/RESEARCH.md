# Quijorna — investigación portal ayuntamiento

Municipio: **Quijorna** (`quijorna`) — Comunidad de Madrid, provincia Madrid.

## URLs base

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://aytoquijorna.org | WordPress (tema citygov). `quijorna.es` / `www.quijorna.es` inaccesible desde cloud |
| Urbanismo | https://aytoquijorna.org/concejalias/urbanismo/ | Índice concejalía |
| Normativa | https://aytoquijorna.org/concejalias/urbanismo/normativa-urbanistica/ | Enlaces a transparencia + BOCM |
| Trámites | https://aytoquijorna.org/concejalias/urbanismo/tramites-y-gestiones-de-urbanismo/ | PDFs guías tramitación (2026) |
| Catálogo actuaciones | https://aytoquijorna.org/concejalias/urbanismo/catalogo-de-procedimientos-y-actuaciones-urbanisticas/ | Procedimientos urbanísticos |
| Sede electrónica | https://aytoquijorna.sedelectronica.es | espublico gestiona / eHome. **Certificado TLS inválido** → `insecure_ssl` |
| Tablón general | https://aytoquijorna.sedelectronica.es/board | Tabla HTML `class_name` + `preview-document` |
| Tablón urbanismo | https://aytoquijorna.sedelectronica.es/board/974e6d5e-f59b-11de-b600-00237da12c6a/ | Enlazado desde web urbanismo |
| Transparencia | https://aytoquijorna.sedelectronica.es/transparency/ | Portal Wicket con carpetas AJAX |

## Cómo se listan expedientes / planeamiento

### WordPress (aytoquijorna.org)

- Páginas estáticas con enlaces a PDFs en `/wp-content/uploads/`.
- Normativa enlaza a dossiers de transparencia en la sede y a publicación BOCM:
  - `BOCM-20210430-21.PDF` (actuaciones sin calificación CM, 2021).
- Trámites: ~20 PDFs de guías (obras mayores/menores, licencias, segregaciones, etc.) — **informativos**, no concesiones.

### Sede espublico — tablón (`/board`)

- Tabla con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- Filas con enlace `preview-document/{uuid}`.
- A julio 2026: pocos anuncios (bandos, IAE); tablón urbanismo con bando limpieza parcelas.

### Sede — transparencia (Wicket AJAX)

Carpetas visibles en HTML (subcarpetas requieren clic AJAX, no scrapeadas en profundidad):

| Dossier UUID | Contenido |
|--------------|-----------|
| `07b48e79-055a-4d36-8e84-13c209f18f6b` | NNSS: 82 docs + acuerdos aprobación (4) + modificaciones (11) |
| `f3a06c71-7022-4309-8f9d-eb96272419be` | Sector 5 (Plan Parcial): Tomos I–IV + Planos |
| `ad88615a-a13d-4576-a91d-63050c8fc9f8` | Ordenanzas complementarias (preview-document directo) |

### Licencias

- No hay listado público de concesiones individuales.
- Guías de tramitación en web + catálogo trámites sede (`/dossier`, requiere sesión).
- Concesiones históricas: tablón cuando se publican edictos.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM Comunidad de Madrid: `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='QUIJORNA'`
  - URL: `https://idem.comunidad.madrid/geoserver3/ows`
- **Estrategia:** `enrich_geometry` + `resolve_ambito_geometry()` por tokens Sector/UE en título (p. ej. «Sector 5», «UE-19»). Sin visor municipal ArcGIS enlazado a expedientes.
- **Limitaciones:**
  - Documentos en transparencia son mayormente PDFs sin georreferencia.
  - Subcarpetas Wicket no expandibles sin sesión AJAX.
  - `quijorna.es` bloqueado/inaccesible; web alternativa `aytoquijorna.org`.
  - Certificado SSL sede inválido.

## Limitaciones generales

- Portal WP accesible solo vía `aytoquijorna.org`.
- Transparencia: carpetas de 1er nivel scrapeables; documentos internos (82 NNSS) requieren navegación Wicket.
- Tablón con escasos anuncios urbanísticos recientes.
- Sin API JSON pública de expedientes.
