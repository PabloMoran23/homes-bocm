# Cadalso de los Vidrios — investigación portal ayuntamiento

**Municipio:** Cadalso de los Vidrios (Comunidad de Madrid)  
**Slug:** `cadalso-de-los-vidrios`  
**INE:** 28031 · **SITCM CD_MUNICIPIO:** 031  
**Fecha:** 2026-08-03  
**BOCM regional (referencia):** 10 avisos

## Resumen

Cadalso de los Vidrios opera con **web corporativa BaseKit** (`123inventatuweb.com`) y **sede electrónica espublico gestiona eHome** (`cadalsodelosvidrios.sedelectronica.es`). El dominio histórico `sedecadalso.eadministracion.es` (Maggioli eAdmin) **ya no resuelve DNS** (NXDOMAIN); anuncios BOCM/BOE que citan ese URL están desactualizados.

Planeamiento vigente: **Normas Subsidiarias** (no PGOU digital municipal). Geometría de ámbitos en **SIT Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`). Sin visor GIS municipal ni datos abiertos urbanísticos.

## URLs relevantes

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | http://www.cadalsodelosvidrios.es/ | BaseKit (123inventatuweb) | Noticias, áreas de gobierno, transparencia parcial |
| Ordenación territorial / urbanismo | http://www.cadalsodelosvidrios.es/áreas-de-gobierno/ordenacion-territorial | HTML | Formularios PDF licencias (enlaces legacy OpenCMS) |
| Medio ambiente y urbanizaciones | http://www.cadalsodelosvidrios.es/áreas-de-gobierno/medio-ambiente-y-urbanizaciones | HTML | Agenda 21, animales domésticos; sin planeamiento |
| Documentos / tablón (redirect) | http://www.cadalsodelosvidrios.es/trámites-y-gestiones/documentos | HTML | Redirige mentalmente al tablón de la sede |
| Normativa municipal | http://www.cadalsodelosvidrios.es/trámites-y-gestiones/normativa-municipal | HTML + Dropbox | Ordenanzas fiscales (tasa licencias urbanísticas, etc.) |
| Portal transparencia (web) | http://www.cadalsodelosvidrios.es/portal-de-transparencia/index | BaseKit | Presupuestos, retribuciones; sin sección urbanismo |
| **Sede electrónica (activa)** | https://cadalsodelosvidrios.sedelectronica.es/ | espublico gestiona / Wicket | Trámites, tablón, transparencia |
| Inicio sede | https://cadalsodelosvidrios.sedelectronica.es/info.0 | HTML | Landing sede |
| Tablón de anuncios | https://cadalsodelosvidrios.sedelectronica.es/board | HTML tabla Wicket | Edictos, convocatorias, BOCM |
| Catálogo trámites | https://cadalsodelosvidrios.sedelectronica.es/dossier.0 | HTML Wicket | Procedimientos (licencias, planeamiento) |
| Transparencia sede | https://cadalsodelosvidrios.sedelectronica.es/transparency | Wicket AJAX | Sección 7 urbanismo: **0 documentos** |
| Consulta expedientes | https://cadalsodelosvidrios.sedelectronica.es/expedientes | Cl@ve | Requiere autenticación |
| Sede eAdmin (obsoleta) | https://sedecadalso.eadministracion.es/ | — | **NXDOMAIN** (citada en BOCM/BOE hasta ~2024) |
| SIT Comunidad de Madrid WFS | https://idem.comunidad.madrid/geoserver3/ows | WFS 2.0 GeoJSON | `sitcm:VPLA_V_AMBITO` |
| BOCM | https://www.bocm.es/ | PDF | Planeamiento, estudios de detalle, licencias puntuales |
| Comunidad de Madrid (OVICAM) | http://www.madrid.org/cs/Satellite?pagename=OVICAM/home_OVICAM&language=es | Portal CM | Formularios vivienda (enlace desde web municipal) |

### Formularios PDF (web — legacy OpenCMS en IP interna)

Enlaces vivos en `ordenacion-territorial` apuntan a `http://176.28.103.6:8080/cadalsodelosvidrios/opencms/...` (probable mirror interno; puede no ser accesible desde fuera):

- Instancia General  
- Solicitud Licencia obra mayor / menor  
- Licencia apertura actividad calificada  

### Trámites urbanísticos en sede (catálogo `dossier.0`)

Procedimientos relevantes (UUID en `/catalog/t/{uuid}`):

- Solicitud de Licencia o Autorización Urbanística  
- Declaración Responsable o Comunicación en Materia Urbanística  
- Solicitud de Modificación o Renuncia de una Licencia Urbanística  
- Solicitud de Actuación Urbanística  
- Solicitud de Aprobación de Planeamiento de Desarrollo  
- Modificación del Planeamiento de Desarrollo / Planeamiento General  
- Solicitud de Certificado o Informe Urbanístico  
- Solicitud de Recepción de Obras de Urbanización  
- Licencia de Actividad / Aprovechamiento / Ocupación / Vado  

## CMS / plataforma detectada

| Componente | Plataforma |
|------------|------------|
| Web municipal | **BaseKit** (`generator: BaseKit`, CDN `123inventatuweb.com`) |
| Sede electrónica | **espublico gestiona eHome** (Apache Wicket, YUI, `meta author: espublico gestiona`) |
| Sede histórica | **Maggioli eAdmin** (`eadministracion.es`) — desmantelada |
| Legacy CMS | **OpenCMS** (rutas PDF en IP 176.28.103.6) |
| Transparencia web | BaseKit (sin datos urbanismo) |
| GIS municipal | **No** (ArcGIS / visor propio / datos abiertos urbanísticos) |

## Tablón de anuncios (`/board`)

Tabla HTML responsive (parser `data-label` como en `torrejon_de_velasco.py`):

- Columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación  
- PDFs vía `preview-document/{uuid}`  
- ~10 anuncios visibles; sin paginación explícita en HTML estático (posible AJAX Wicket para más)  
- Búsqueda por texto y filtro por tipo de anuncio (form Wicket)

**Muestra vigente (ago 2026):** convocatorias de pleno, IBI, bolsas de trabajo, ordenanza convivencia, cesión patrimonial — **sin licencias urbanísticas en tablón activo** en el momento de la investigación.

## Licencias — cómo se publican

1. **Tablón sede** (`/board`): edictos de licencia cuando el ayuntamiento publica el anuncio (patrón espublico estándar). Categoría «Licencias Urbanísticas» cuando aplica.  
2. **BOCM**: aprobaciones de planeamiento, estudios de detalle, licencias con trámite de información pública (ej. UA-b estudio de detalle, BOCM 14-may-2026).  
3. **Web municipal**: solo formularios de solicitud (PDF), no listado de concesiones.  
4. **Consulta expedientes** en sede: requiere Cl@ve; no scrapeable.  
5. **No hay** dataset abierto de licencias con dirección/coordenadas (como Madrid capital / SIGMA).

## Planeamiento / proyectos

- Figura vigente: **Normas Subsidiarias** (aprobación histórica BOE 1977/1985).  
- Ámbitos SITCM: sectores **S-1…S-4**, unidades de actuación **UA-A…UA-H** (12 polígonos).  
- Actividad reciente BOCM: Estudio de Detalle **UA-b** (definitiva may-2026); Plan Especial Infraestructuras aducción (inic. ene-2025).  
- Sin PGOU / planos descargables en web municipal.  
- Transparencia sede sección 7 (urbanismo): vacía (0 docs).

## GIS / SITCM

- **SITCM WFS aplica:** sí (municipio en CCAA Madrid, capa `sitcm:VPLA_V_AMBITO`).  
- **Filtro:** `DS_MUNICIPIO='CADALSO DE LOS VIDRIOS'` (CD_MUNICIPIO `031`).  
- **Ámbitos:** 12 polígonos EPSG:4326 — `S-1`, `S-2`, `S-3`, `S-4`, `UA-A`…`UA-H`.  
- **geometry_status:** `partial`  
- **Estrategia:** cruzar título/expediente BOCM o tablón con código de ámbito (`S-*`, `UA-*`) y resolver polígono vía WFS; licencias puntuales y estudios de detalle sin código en WFS → sin geometría o centroid municipal.  
- **Limitaciones:** sin visor municipal; transparencia urbanismo vacía; tablón sin georreferencia; estudios de detalle (UA-b) no aparecen como capa WFS separada.

## Estrategia de scraping recomendada

Patrón **espublico + SITCM partial**, alineado con `torrejon_de_velasco.py`, `san_martin_de_la_vega.py`, `valdemorillo.py`:

1. **Tablón** `GET /board` (sesión vía `/info.0` si hace falta cookies) → parser tabla `data-label` → `preview-document/{uuid}`.  
2. **Filtros regex** licencia / proyecto / exclude (fiscal, personal, IBI) como adapters vecinos.  
3. **Catálogo trámites** `dossier.0`: páginas informativas de procedimientos urbanísticos (`/catalog/t/{uuid}`) — metadata, no expedientes.  
4. **Web BaseKit:** PDFs formulario en `ordenacion-territorial` + ordenanza tasa licencias en `normativa-municipal` (licencias informativas).  
5. **BOCM** (`bocm` en manifest): match proyectos/licencias no publicados en tablón.  
6. **Geometría:** `municipio.gis.sitcm` — `resolve_municipio_wfs('Cadalso de los Vidrios')` + match `DS_NOMB_AMB` por tokens (`S-3`, `UA-B`, etc.).  
7. **IDs:** `cadalso-de-los-vidrios-{lic|proy}-{sha256[:14]}`.  
8. **No intentar** `sedecadalso.eadministracion.es` (dominio caído).

## Limitaciones

- Dominio eAdmin obsoleto en publicaciones oficiales recientes.  
- Tablón muestra ventana corta (~10 ítems); histórico vía búsqueda Wicket o BOCM.  
- Transparencia urbanismo sede vacía.  
- PDFs legacy en IP interna OpenCMS pueden fallar fuera de red municipal.  
- `https://www.cadalsodelosvidrios.es` sin respuesta; usar `http://www.cadalsodelosvidrios.es`.  
- Sin ArcGIS REST, GeoJSON municipal ni datos abiertos urbanísticos.

## Referencia adapters

- Tablón espublico: `torrejon_de_velasco.py`, `san_martin_de_la_vega.py`, `humanes_de_madrid.py`  
- WFS SITCM partial: `valdilecha.py`, `torrejon_de_velasco.py`, `patones.py`  
- eAdmin obsoleto + web PDFs: `valdilecha.py` (patrón híbrido)
