# Cuéllar — investigación portal ayuntamiento

**Municipio:** Cuéllar (Segovia, Castilla y León)  
**Slug:** `cuellar`  
**Boletín:** BOCYL (`bocm_count`: 6)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://www.aytocuellar.es |
| Urbanismo | https://www.aytocuellar.es/urbanismo/ |
| Normas Urbanísticas Municipales (NUM) | https://www.aytocuellar.es/urbanismo/normas-urbanisticas-municipales/ |
| Oficina Técnica Municipal | https://www.aytocuellar.es/urbanismo/oficina-tecnica-municipal/ |
| Categoría WP «información urbanismo» | https://www.aytocuellar.es/category/informacion-urbanismo/ |
| Sede electrónica (espublico) | https://cuellar.sedelectronica.es |
| Tablón de anuncios | https://cuellar.sedelectronica.es/board |
| Visor planeamiento CyL (IDECyL) | https://idecyl.jcyl.es/visor/urbanismo |

**Nota:** `www.cuellar.es` responde vacío (403 en rutas PHP); el dominio operativo del ayuntamiento es `aytocuellar.es`.

## Cómo se listan expedientes / proyectos

1. **WordPress REST API** (`/wp-json/wp/v2/posts`, `/pages`): noticias de convenios urbanísticos, modificaciones NUM, información pública. Categoría dedicada `informacion-urbanismo` (6 entradas).
2. **PDFs embebidos** en posts y páginas de urbanismo (convenios BOCYL, anuncios).
3. **Tablón sede espublico** (`/board`): tabla HTML con expediente, procedimiento, categoría y enlace `preview-document/{uuid}` a PDFs. Incluye ordenanzas fiscales de licencias ambientales.
4. **IDECyL WFS** (PLAU CyL): instrumentos, planes parciales y sectores del municipio con geometría.

No hay visor municipal propio ni listado estructurado de expedientes urbanísticos individuales más allá del tablón y las noticias.

## Licencias de obra

- No hay dataset ni cartel periódico de licencias concedidas.
- El tablón publica ordenanzas sobre tasas de licencias ambientales (p. ej. BOP Segovia 28-01-2026).
- Trámites informativos en sede electrónica y sección urbanismo.
- **Estrategia adapter:** páginas informativas de trámite + entradas del tablón que mencionen «licencia».

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun = 'Cuéllar'`
  - Salida: GeoJSON EPSG:4326 (`outputFormat=application/json`, `srsName=EPSG:4326`)
  - Resultados: 1 instrumento (NUM), 2 planes parciales, 5 sectores (8 polígonos)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer posts WP/tablón por coincidencia de título (sector, PAS-C, etc.).
- **Limitaciones:** convenios urbanísticos recientes (Mercadona, Piedras Granjales) solo tienen PDF sin enlace GIS; geometría parcial vía sectores WFS cuando el título coincide.

## Limitaciones generales

- Dominio `cuellar.es` inactivo para scraping directo.
- Tablón mezcla urbanismo con empleo, fiestas, padrones — filtrado por regex.
- Sin API de expedientes urbanísticos individuales.
- Licencias concedidas no publicadas de forma tabular.
