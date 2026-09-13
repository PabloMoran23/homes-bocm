# Covarrubias — investigación portal ayuntamiento

Municipio: Covarrubias (Burgos, Castilla y León). Código INE: `09113` (provincia `09`, municipio `113`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.covarrubias.es | Drupal 10, tema Toools (patrón Diputación Burgos) |
| Sede electrónica | https://covarrubias.sedelectronica.es | espublico gestiona — tablón, trámites |
| Tablón de anuncios | https://covarrubias.sedelectronica.es/board | Anuncios Wicket (contrataciones en muestra actual) |
| Catálogo trámites | https://covarrubias.sedelectronica.es/dossier | 113 trámites; licencias y actuaciones urbanísticas |
| Información general | https://www.covarrubias.es/informacion-general | Enlace al archivo PLAU JCyL |
| Normativa | https://www.covarrubias.es/normativa | Ordenanzas generales (sin PDFs urbanísticos embebidos) |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=113 | 13 instrumentos aprobados (NUM, PECH, ED, PORN, PN) |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=113 | Sin expedientes en información pública al investigar |

## Expedientes / proyectos

- **Principal:** archivo PLAU Junta de Castilla y León — tabla HTML con Libro, Instrumento, fechas y título. Documentos vía `doGoBoletin('id')` → `openBoletin.do?cDocId=`.
- **Geometría:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Covarrubias'` (1 instrumento de ámbito, 9 sectores).
- **Tablón sede:** sin anuncios urbanísticos recientes (solo contrataciones patrimoniales).
- **Web Drupal:** sin sección `/urbanismo` dedicada; planeamiento referenciado vía JCyL en información general.

Instrumentos PLAU identificados (muestra): NORMAS URBANÍSTICAS MUNICIPALES, modificaciones NUM, Plan Especial del Conjunto Histórico (PECH), estudios de detalle (Avda. Víctor Barbadillo, SU-1 Las Eras), PORN Sabinares del Arlanza, proyecto normalización UA Avda. Víctor Barbadillo 21.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón.
- Trámites informativos en sede (`/dossier`): solicitud de licencia urbanística, comunicación/declaración responsable urbanística, licencia de ocupación, recepción de obras, etc.
- El adapter devuelve páginas informativas de trámite cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Covarrubias'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PLAU por coincidencia de título o códigos sector (SU-1, UA 2B, etc.).
- **Limitaciones:** sin visor municipal ArcGIS; licencias sin georreferencia; geometría WFS a nivel instrumento/sector, no expediente individual; sede raíz redirige en bucle (board/dossier accesibles directamente).

## Limitaciones

- Tablón espublico sin categoría urbanismo activa con expedientes recientes.
- Drupal sin descargas PDF urbanísticas en rutas estándar.
- PLAU: dependencia de HTML legacy JCyL.
- SSL sede: adapter usa `insecure_ssl` por compatibilidad con certificado espublico.
