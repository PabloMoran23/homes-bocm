# Huerta de Rey — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `huerta-de-rey` |
| Provincia | Burgos (Castilla y León) |
| INE | 09177 |
| Boletín | BOCYL (`bocyl`) |
| Web | https://www.huertaderey.es (Drupal 10, tema Toools) |
| Sede | https://huertaderey.sedelectronica.es (espublico gestiona) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.huertaderey.es | Drupal Toools; noticias municipales |
| Noticias | https://www.huertaderey.es/noticias | ~12 artículos; varios de urbanismo (estudios de detalle, aprobaciones) |
| Sede electrónica | https://huertaderey.sedelectronica.es | Trámites, tablón, transparencia |
| Tablón anuncios | https://huertaderey.sedelectronica.es/board | Tablón espublico (poco contenido urbanístico) |
| Trámites OBRAS | https://huertaderey.sedelectronica.es/citizen-service/d9f26e4d-e46d-4a6c-8a50-f5e2d15e1ca1 | Obra mayor/menor, licencias urbanísticas |
| PLAU CyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=174 | 14 documentos aprobados (NUM, PP, ED, PERI, PAU…) |
| PLAI CyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=174 | Sin documentos en información pública |
| Diputación Burgos | https://www.burgos.es/provincia/municipio/huerta-de-rey | Ficha municipal; enlace archivo planeamiento |

## Proyectos / expedientes urbanísticos

### PLAU CyL (fuente principal)

Listado HTML tabular en PlanPublica. Columnas: Libro, Tipo, Fecha publicación, Fecha aprobación, Título.

Documentos relevantes (selección):

- NORMAS URBANÍSTICAS MUNICIPALES (NUM, 2014)
- PP RESIDENCIAL R-2, PP USO INDUSTRIAL LAS ANEGUILLAS
- ESTUDIO DE DETALLE paraje El Castillo (2025)
- ESTUDIO DE DETALLE C/. Camino del Salcejo, C/. Caridad
- PERI C/ Camino del Salce nºs 13, 15 y 17
- MODIFICACIONES NUM (alineaciones, AA-UN 3…)

Enlaces PDF: `openDocumento.do?cDocId=…` / `openDocuIndice.do?cDocId=…`

### Web Drupal (noticias)

Artículos sobre aprobaciones urbanísticas publicados como noticias:

- Aprobación definitiva estudio de detalle paraje El Castillo
- Aprobación inicial estudio de detalle paraje del Castillo
- (Otros: alumbrado LED, emprendedores — excluidos del scrape urbanístico)

### Tablón sede

Solo 1 aviso activo (pliego albergue — no urbanismo). Sin licencias ni expedientes urbanísticos recientes.

## Licencias de obra

No hay dataset público de licencias concedidas. Fuentes informativas:

- Sede → Servicios en línea → OBRAS: obra mayor (licencia/autorización urbanística) y obra menor (declaración responsable)
- Contacto: huertaderey@diputaciondeburgos.net, 947 388 001

El adapter devuelve páginas informativas de trámites (patrón Pozuelo/Espinosa).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NUM MultiPolygon), `urbanismo:plau_cyl_sectores` (9 sectores)
  - Filtro: `CQL_FILTER=n_mun = 'Huerta de Rey'`
  - `outputFormat=application/json`, `srsName=EPSG:4326`
- **Estrategia:** consulta WFS por municipio; enriquecer proyectos PLAU/WFS con `geom_geojson` del sector o instrumento coincidente por título/código
- **Limitaciones:**
  - Estudios de detalle y modificaciones puntuales no tienen polígono individual en WFS (solo instrumentos/sectores)
  - Tablón y noticias Drupal sin georreferencia
  - Sin visor ArcGIS municipal propio

## Limitaciones generales

- Tablón casi vacío (sin bandos de licencias)
- PLAI sin documentos activos
- Web sin sección /urbanismo dedicada; planeamiento en PLAU CyL
- Sede requiere cookie warm-up para algunos endpoints (dossier)
