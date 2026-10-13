# Pomar de Valdivia — investigación portal ayuntamiento

**Slug:** `pomar-de-valdivia`  
**Provincia:** Palencia (Castilla y León)  
**INE:** 34135  
**Boletín:** BOCYL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://pomardevaldivia.es | WordPress (plantilla Diputación de Palencia / Divi) |
| Urbanismo (galería) | https://pomardevaldivia.es/ayuntamiento/urbanismo/ | Subsecciones `?g=10&st=0..2` (planeamiento) y `?g=20` (licencias) |
| Sede electrónica | https://pomardevaldivia.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://pomardevaldivia.sedelectronica.es/board | PDFs `preview-document` (poco urbanismo; mayoría tributos) |
| Catálogo trámites | https://pomardevaldivia.sedelectronica.es/dossier | Trámites urbanísticos (warm-up tras tablón) |
| PLAU Junta CYL | http://servicios.jcyl.es/PlanPublica/lplanes.plau?municipio=3413560006901 | Índice planeamiento aprobado |
| PLAI (info pública) | searchVPubDocMuniPlai.do?provincia=34&municipio=135 | Consulta IP |
| PLAU (archivo) | searchVPubDocMuniPlau.do?provincia=34&municipio=135 | Documentos aprobados (p. ej. modificación Revilla de Pomar) |
| Entradas WP urbanismo | `/urbanismo/modificacion-normas-urbanisticas/` | PDFs vía Download Monitor |

## Expedientes / planeamiento

- **Galería WP:** títulos en atributos `title` de imágenes/documentos en páginas `?g=10&st=N`.
- **Download Monitor:** enlaces `/index.php/download/<id>/` en sección licencias (`g=20`) y posts de modificación normativa.
- **IDECyL WFS:** instrumentos de planeamiento y sectores con polígono para `n_mun='Pomar de Valdivia'`.
- **PlanPublica:** código municipio **135** (provincia **34** Palencia).

## Licencias de obra

- No hay listado público de concesiones en tablón (anuncios tributarios/padrón).
- **Catálogo sede:** páginas informativas de trámites de licencia/comunicación previa (patrón espublico).
- Sección WP `g=20` documenta modelos/actos de intervención en el suelo (PDFs).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun='Pomar de Valdivia'`
- **Estrategia:** ingestar geometría desde WFS (`EPSG:4326`); enriquecer filas galería/tablón por código sector o match título ↔ sector WFS.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin GIS; tablón mayoritariamente no urbanístico.

## Limitaciones generales

- REST API WP deshabilitada (`401 No REST API`).
- Galería urbanismo depende de HTML estático (sin API JSON pública).
- Sede dossier puede ser lento; `insecure_ssl: true` por compatibilidad certificados sede.
