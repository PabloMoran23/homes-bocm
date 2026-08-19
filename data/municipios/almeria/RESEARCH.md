# Almería — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.almeriaciudad.es |
| Urbanismo | https://www.almeriaciudad.es/urbanismo |
| Tablón (área Urbanismo, `area=4`) | https://www.almeriaciudad.es/tablon-de-anuncios?type=All&area=4 |
| Obras públicas y PGOU (PDFs) | https://www.almeriaciudad.es/obras-publicas-y-urbanismo |
| Trámites GMU | https://www.almeriaciudad.es/urbanismo/tramites-y-gestiones |
| Información técnica urbanismo | https://www.almeriaciudad.es/urbanismo/informacion-tecnica-de-urbanismo |
| Sede electrónica (STA) | https://sede.aytoalmeria.es — **inaccesible** (connection reset) |
| Visor PGOU municipal | Incorporado en web (noticia 2024); enlace directo no localizado en HTML estático |
| Geoportal Diputación | https://app.dipalme.org/visor-gis/ |

## CMS y listado de expedientes

- **CMS:** Drupal en `almeriaciudad.es` (vistas `adet-views-list`, meta `<time datetime="...">`).
- **Proyectos:** Tablón filtrado por área 4 (Gerencia Municipal de Urbanismo). Paginación `&page=N` (~10 páginas).
- **Documentos PGOU:** PDFs enlazados en `/obras-publicas-y-urbanismo` (`/uploads/media/document/*.pdf`).
- **Sede STA:** Tablón `PTS2_TABLON` y expedientes requieren certificado / bloqueados desde red del agente.

## Licencias

- No hay listado público de licencias concedidas en el tablón ni en la web consultable.
- Trámites informativos en `/urbanismo/tramites-y-gestiones` e `/urbanismo/informacion-tecnica-de-urbanismo`.
- La sede electrónica publicaría edictos/licencias pero no es accesible para scraping automatizado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación: `https://app.dipalme.org/geoserver/urbanismo/ows`
  - Capa: `urbanismo:v_siu_ambitos_o_sectores`
  - Filtro municipio: `cod_ine='04013'` (Almería capital)
  - Campo enlace: `sector` (nombre del ámbito/sector SIU, 125 polígonos)
  - Salida: GeoJSON con `srsName=EPSG:4326`
- **Estrategia:** Tras obtener metadatos del tablón/PDF, buscar coincidencia del nombre de sector en el título del proyecto y adjuntar el polígono WFS correspondiente.
- **Limitaciones:**
  - No hay geometría por expediente individual; solo sectores/ámbitos del planeamiento general (SIU).
  - Sede y visor municipal PGOU no consultables desde el agente.
  - Certificado SSL inválido en `almeriaciudad.es` → `insecure_ssl: true`.
  - Muchos anuncios no mencionan sector explícito → sin polígono.

## Limitaciones generales

- `sede.aytoalmeria.es`: connection reset (no tablón STA ni catálogo de trámites).
- Sin API JSON pública del tablón (`_format=json` → 406).
- Licencias: solo páginas informativas, no concesiones publicadas.
