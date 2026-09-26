# Benavente — investigación portal ayuntamiento

Municipio: **Benavente** (`benavente`), provincia Zamora, Castilla y León. INE 49021.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://benavente.es | WordPress + Elementor (Hello theme) |
| Urbanismo | https://benavente.es/areas-municipales/urbanismo-infraestructuras-obras-y-servicios/ | PGOU, modificaciones, ~190 PDFs (plaupdf JCyL + BOCYL) |
| Tablón anuncios | https://benavente.es/actualidad/anuncios/ | Anuncios paginados (Elementor h1 + PDF adjunto) |
| Trámites | https://benavente.es/tramites/ | Enlaces a sede y trámites generales |
| Sede electrónica | https://aytobenavente.org | espublico/gestiona — **503 Service Unavailable** desde CI |
| Sede alternativa | https://benavente.sedelectronica.es | Página «sede indeterminada» (sin board) |
| PLAU JCyL | https://servicios.jcyl.es/PlanPublica/ (provincia=49) | Índice planeamiento CYL; documentos PGOU enlazados desde web |

**Nota SSL:** `www.benavente.es` presenta certificado inválido; `benavente.es` responde con `insecure_ssl`.

## Cómo se listan expedientes / proyectos

1. **IDECyL WFS** (`urbanismo:plau_cyl_*`): sectores, planes parciales e instrumentos de ámbito del PGOU de Benavente (~60 sectores). JSON GeoJSON en EPSG:4326, filtro `n_mun = 'Benavente'`.
2. **Página urbanismo WP:** listado estático de PDFs del PGOU, modificaciones puntuales, estudios y documentación histórica (enlaces `plaupdf` JCyL y BOCYL).
3. **Tablón anuncios WP:** posts Elementor con título h1 y PDF en `wp-content/uploads/`; paginación `/actualidad/anuncios/N/`.
4. **Sede espublico:** no accesible (503); no se usa en el adapter.

## Cómo se publican licencias

- No hay dataset abierto de concesiones de licencia con coordenadas.
- El tablón de anuncios publica avisos puntuales (autorizaciones, memorias); la mayoría son empleo/becas (excluidos).
- Páginas informativas de trámites en `/tramites/` y área de urbanismo.
- El adapter devuelve filas informativas de trámite + licencias detectadas en anuncios (p. ej. «MEMORIA AUTORIZACION USO ASTEO»).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Benavente'`, campos `n_num_sect`, `c_id_sect`, `n_sector`
  - Cartografía PGOU en DWG en web (`benavente.es/wp-content/uploads/2025/03/*.dwg`) — no parseada
  - Referencia codificación: `www.benavente.es/urbanismo/pgou/cartografia_1000/CODIFICA.TXT` (SSL inválido en www)
- **Estrategia:** ingestar polígonos WFS como proyectos con `geom_geojson`; enriquecer PDFs/anuncios con `_attach_geometry` por código de sector (`S-6IN`, etc.).
- **Limitaciones:** licencias y anuncios sin enlace GIS; sede bloqueada; DWG no convertidos; expedientes individuales sin polígono salvo match por sector WFS.

## Limitaciones generales

- Sede `aytobenavente.org` devuelve 503 (F5) en entorno CI — tablón espublico no scrapeable.
- `benavente.sedelectronica.es` sin sede asignada.
- Certificado SSL inválido en `www.benavente.es`.
- Anuncios mezclan urbanismo con empleo/becas; filtrado por regex.
- PLAU portal JCyL no indexa fácilmente por código municipal único (documentos PGOU accesibles vía web municipal).
