# Villavieja del Lozoya — investigación portal ayuntamiento

**Slug:** `villavieja-del-lozoya`  
**Nombre oficial:** Villavieja del Lozoya  
**BOCM (referencia):** 15 anuncios  
**Fecha investigación:** 2026-07-10

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (WordPress, tema sport-child) | https://villaviejadellozoya.es | Accesible |
| Sede electrónica (espublico gestiona / eHome) | https://villaviejadellozoya.sedelectronica.es | Accesible |
| Turismo | http://turismo.villaviejadellozoya.es | Accesible (no urbanismo) |

## Fuentes de datos

### 1. Tablón municipal (WordPress REST)

- **Categoría:** `tablon-municipal` (id 39, ~273 entradas).
- **API:** `https://villaviejadellozoya.es/wp-json/wp/v2/posts?categories=39&per_page=100`
- **Formato:** JSON REST; título, fecha, enlace, contenido HTML con PDFs/imágenes embebidos.
- **Contenido urbanístico:** ~37 anuncios con palabras clave (licencias, expedientes ruina, NNSS, obras, información pública).
- **Uso:** `proyectos.jsonl` y `licencias.jsonl` filtrando título/contenido.

### 2. Urbanismo / planeamiento (WordPress)

| Página | URL | Contenido |
|--------|-----|-----------|
| Normas subsidiarias | `/urbanismo/normas-subsidiarias/` | PDFs NNSS (acuerdo, catálogo, memoria, normas, planos) + enlace visor SIT CM |
| Avance PGOU | `/avance-del-plan-general-de-villavieja-del-lozoya/` | Documento avance + planos información/ordenación (2018) |
| Categoría urbanismo | `/category/urbanismo/` | 1 entrada (avance PGOU) |

- **Formato:** WPBakery/accordion con enlaces directos a `/wp-content/uploads/*.pdf`.
- **Uso:** `proyectos.jsonl` (PGOU, NNSS, planeamiento).

### 3. Tablón sede electrónica (espublico)

- **URL:** https://villaviejadellozoya.sedelectronica.es/board
- **Formato:** Wicket/YUI; tabla con `preview-document` cuando hay filas.
- **Estado (2026-07-10):** HTML sin filas de datos (0 `preview-document`); listado probablemente vacío o cargado por AJAX sin datos públicos indexables.
- **Trámites urbanismo:** `/citizen-service/3a1af47f-df38-4c0d-bb75-14bdd8bb2edb` (URBANISMO).
- **Uso:** scrape defensivo; páginas informativas de trámites para licencias.

### 4. Consulta expedientes

- **URL:** `/expedientes` — requiere identificación Cl@ve; sin listado público.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SIT Comunidad de Madrid (enlace en normas subsidiarias): https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente/sistema-informacion-territorial-visor-sit
  - WFS GeoServer CM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VILLAVIEJA DEL LOZOYA'`
  - Campo ámbito: `DS_NOMB_AMB`
- **Ámbitos (10):** UE-B, UE-A-1/2/3, ACTUACIÓN AISLADA 1/2, TERCIO DE LA LAGUNA, LA CAÑADA, LAS CABEZAS, EL MOLINILLO
- **Estrategia:** descarga WFS con `srsName=EPSG:4326`; emparejamiento heurístico título ↔ `DS_NOMB_AMB` (UE-*, urbanizaciones locales).
- **Limitaciones:** tablón/PDF sin código UE explícito en la mayoría de anuncios; licencias sin polígono; visor SIT no enlaza expediente individual.

## Estrategia de ingesta

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | Tablón WP REST (urbanismo) | PDFs NNSS/PGOU + sede board |
| `licencias.jsonl` | Tablón WP (solicitudes/licencias) | Trámites sede URBANISMO |

IDs estables: `villavieja-del-lozoya-{lic|proy}-{sha256[:14]}`.

## Limitaciones conocidas

- Tablón sede espublico sin filas scrapeables en HTML estático.
- Sin dataset público de licencias concedidas con coordenadas.
- Muchos anuncios del tablón WP son fiscales/recaudación (excluidos por filtros).
- Geometría SIT solo aplica a ámbitos de planeamiento, no a expedientes puntuales del tablón.
