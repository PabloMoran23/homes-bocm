# Horcajo de la Sierra — investigación portal ayuntamiento

**Municipio:** Horcajo de la Sierra-Aoslos (Comunidad de Madrid)  
**Fecha:** 2026-09-18  
**BOCM regional (referencia):** 1 aviso (`queue.yaml`)

## Resumen

Horcajo de la Sierra-Aoslos es un municipio unificado (Horcajo de la Sierra + Aoslos) cuya web oficial es
**Joomla** (`www.horcajodelasierra-aoslos.es`, plantilla Helix3 / SP Page Builder) y cuya sede electrónica
es **espublico gestiona** (`horcajodelasierra-aoslos.sedelectronica.es`, Apache Wicket).

No existe visor urbanístico municipal propio. El planeamiento vigente y su geometría están en el
**SIT de la Comunidad de Madrid** (código municipio SIT `070`, `codMunZona=0702`). Los expedientes
urbanísticos individuales **no se publican** en listados abiertos: solo hay trámites informativos en la
sede, formularios PDF descargables y anuncios puntuales en el tablón municipal.

**Nota de dominio:** `www.horcajodelasierra.es` / `horcajodelasierra.es` **no resuelven DNS**.
El dominio oficial es `horcajodelasierra-aoslos.es`.

## URLs oficiales

| Rol | URL |
|-----|-----|
| Web corporativa | `https://www.horcajodelasierra-aoslos.es/` |
| Sede electrónica | `https://horcajodelasierra-aoslos.sedelectronica.es/` |
| Catálogo de trámites | `https://horcajodelasierra-aoslos.sedelectronica.es/dossier.0` (redirect desde `/dossier`) |
| Tablón sede | `https://horcajodelasierra-aoslos.sedelectronica.es/board` |
| Transparencia sede | `https://horcajodelasierra-aoslos.sedelectronica.es/transparency` |
| Urbanismo (formularios) | `https://www.horcajodelasierra-aoslos.es/ciudadanos/tramites-personales/urbanismo` |
| Tablón municipal | `https://www.horcajodelasierra-aoslos.es/ciudadanos/tablon-municipal` |
| Tablón RSS | `https://www.horcajodelasierra-aoslos.es/ciudadanos/tablon-municipal?format=feed&type=rss` |
| PGOU / planeamiento | `https://www.horcajodelasierra-aoslos.es/tu-ayuntamiento/normativa-municipal/plan-general-de-urbanismo` |
| Ordenanzas municipales | `https://www.horcajodelasierra-aoslos.es/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales` |
| Visor SIT (enlace PGOU) | `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=070` |
| Ficha municipal CM | `https://gestiona.comunidad.madrid/desvan/almudena/FichaMunicipal.icm?codMunZona=0702` |

## Patrón técnico

| Componente | Plataforma | Detalles |
|------------|------------|----------|
| Web municipal | **Joomla 3.x** | `com-content`, Helix3 (`shaper_helix3`), icagenda, dearflip PDF viewer, JCE mediabox |
| Tablón municipal | Joomla categoría | Tabla HTML paginada (`?start=N`, 20 ítems/página), RSS/Atom |
| Sede electrónica | **espublico gestiona** | Apache Wicket + YUI; URLs con token `?x=…`; sesión `JSESSIONID` |
| Tablón sede | espublico board | Tabla Wicket: Documento / Expediente / Procedimiento / Categoría / Descripción / Fecha |
| Transparencia | espublico | Árbol documental; sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con **0 documentos** |
| GIS planeamiento | **SIT Comunidad de Madrid** | GeoServer WFS `idem.comunidad.madrid/geoserver3/ows`; visor ArcGIS web SITCM |

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://www.horcajodelasierra-aoslos.es` | Joomla | Menú, normativa, tablón, trámites PDF |
| Urbanismo trámites | `/ciudadanos/tramites-personales/urbanismo` | Joomla + PDFs estáticos | Obra mayor, primera ocupación, devolución fianza, DR urbanística |
| Tablón municipal | `/ciudadanos/tablon-municipal` | Joomla + RSS | ~133 artículos; PDFs/imágenes embebidos |
| Tablón sede | `/board` | HTML espublico | Tabla vacía (solo cabeceras, sept 2026) |
| Catálogo trámites sede | `/dossier.0` | HTML espublico | Fichas informativas por procedimiento (UUID en `/catalog/t/{uuid}`) |
| Transparencia | `/transparency` | HTML espublico | Sin documentos en urbanismo |
| Ordenanzas urbanísticas | `/tu-ayuntamiento/normativa-municipal/ordenanzas-municipales/443-…` etc. | Joomla + dearflip PDF | Títulos habilitantes, tasas licencias urbanísticas |
| PGOU | `/tu-ayuntamiento/normativa-municipal/plan-general-de-urbanismo` | Joomla texto + enlace SIT | Redirige al visor SIT municipio 070 |
| SIT WFS refundido | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS 2.0 | Capas `sitcm:VPLA_V_*_REF_23` filtro `CD_MUNICIPIO='070'` |
| Visor SIT | `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=070` | ArcGIS web | Planeamiento + PDFs legales escaneados |
| BOCAM / BOCM | Boletín comarcal/regional | PDF | Ordenanzas publicadas (p. ej. BOCAM nº 205, 8-sep-2021) citadas en formularios |

### Formularios PDF urbanismo (descarga directa)

| Trámite | URL |
|---------|-----|
| Licencia obra mayor | `https://www.horcajodelasierra-aoslos.es/images/ciudadanos/tramites/urbanismo/02-04-SolicitudLicenciaObraMayor.pdf` |
| Licencia primera ocupación | `https://www.horcajodelasierra-aoslos.es/images/ciudadanos/tramites/urbanismo/12-15.SolicitudLicenciaPrimeraOcupacion.pdf` |
| Devolución fianza licencia obra | `https://www.horcajodelasierra-aoslos.es/images/ciudadanos/tramites/urbanismo/DEVOLUCION_FIANZA_LICENCIA_DE_OBRA15112013.pdf` |
| Declaración responsable urbanística | `https://www.horcajodelasierra-aoslos.es/images/ciudadanos/tramites/urbanismo/declaracion_responsable_urbanistica.pdf` |

### Trámites sede relevantes (catálogo informativo, no concesiones)

Accesibles vía `https://horcajodelasierra-aoslos.sedelectronica.es/dossier.0` → sección «Urbanismo y Vivienda»:

| Trámite | URL catálogo |
|---------|--------------|
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Modificación o Renuncia de una Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Solicitud de Declaración de Ruina | `/catalog/t/e64a8029-2e12-49aa-a002-120e27ca1386` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Solicitud de Aprobación de Planeamiento de Desarrollo | `/catalog/t/23c80d53-bdad-47a5-b731-f786c411e08d` |
| Solicitud de Recepción de Obras de Urbanización | `/catalog/t/e8594295-30ea-4a16-8f17-60c061a8a147` |

La consulta de expedientes en curso (`/expedientes`) requiere **identificación** (Cl@ve / certificado).

## Cómo se listan expedientes / proyectos

- **No hay** listado público estructurado de expedientes urbanísticos ni proyectos en tramitación.
- **Planeamiento:** página PGOU con enlace al visor SIT; ordenanzas urbanísticas como artículos Joomla con PDF embebido (dearflip).
- **Tablón municipal Joomla:** artículos paginados (`?start=0,20,40…`) con título, fecha, cuerpo HTML y PDF/imagen adjuntos.
  - ~133 artículos totales; ~12 con keywords urbanísticas (infracciones, bandos licencia fiestas, normativa rural).
  - Ejemplos: `/ciudadanos/tablon-municipal/316-notificacion-infraccion-urbanistica` (PDF BOCM 2018).
- **Tablón sede espublico:** estructura tabular determinista pero **sin filas publicadas** (sept 2026).
- **Transparencia:** sección urbanismo vacía.
- **Plenos:** menú «Actas de Plenos Municipales» apunta a `javascript:void(0)` (sin listado accesible).
- **No hay** API JSON, visor propio ni dataset de expedientes.

## Cómo se publican licencias

| Canal | Estado | Formato |
|-------|--------|---------|
| Tablón municipal Joomla | Activo, esporádico | Artículos + PDF/imagen; RSS disponible |
| Tablón sede `/board` | Vacío | Tabla HTML Wicket (cuando hay datos: columnas deterministas) |
| Sede catálogo `/dossier.0` | Solo informativo | Fichas de procedimiento; no historial de concesiones |
| Web `/urbanismo` | Formularios | PDFs descargables para presentación presencial |
| Dataset / CSV | No existe | — |
| BOCAM / BOCM | Regional | Ordenanzas y algunos anuncios (p. ej. infracciones urbanísticas) |

No se encontró registro histórico de licencias concedidas con fecha, dirección, referencia catastral ni coordenadas.
Las licencias de obra se tramitan presencialmente (horario 9–14 h) o vía sede con identificación; la publicidad
de concesión, cuando existe, sería en tablón (Joomla o sede) como PDF escaneado.

## Geometría / visor

- **geometry_status:** `partial`
- **Nombre SIT:** `HORCAJO DE LA SIERRA-AOSLOS` (`CD_MUNICIPIO=070`, `codMunZona=0702`)
- **Visor:** `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=070`
- **WFS base:** `https://idem.comunidad.madrid/geoserver3/ows`

### Capas WFS verificadas (sept 2026)

| Capa | Filtro `CD_MUNICIPIO='070'` | Features | Notas |
|------|------------------------------|----------|-------|
| `sitcm:VPLA_V_AMBITO` (vigente) | `DS_MUNICIPIO='HORCAJO DE LA SIERRA-AOSLOS'` | **0** | Sin ámbitos en capa vigente |
| `sitcm:VPLA_V_AMBITO_REF_23` (refundido 2023) | `CD_MUNICIPIO='070'` | **1** | `UE-1` (Polygon) |
| `sitcm:VPLA_V_ORDENANZA_REF_23` | `CD_MUNICIPIO='070'` | **10** | `CASCO ANTIGUO` (polígonos) |
| `sitcm:VPLA_V_RED_REF_23` | `CD_MUNICIPIO='070'` | **21** | Redes: VIARIO, VERDE PÚBLICO, EQUIPAMIENTOS, etc. |

`resolve_municipio_wfs()` del helper `municipio/gis/sitcm.py` (capa `VPLA_V_AMBITO`) devuelve `None` para
este municipio; hay que usar capas **refundidas** (`*_REF_23`) o `ILIKE '%HORCAJO%SIERRA%'` en `VPLA_V_AMBITO_REF_23`.

### Datos abiertos CM

- Catálogo IDEM: `https://idem.comunidad.madrid/catalogocartografia/srv/spa/catalog.search#/home` (keyword «Planeamiento Urbanístico»)
- Feed ATOM refundido 2023: `https://idem.comunidad.madrid/recursos_cat_geo/Catalogo/atom/dataset_feeds/planeamiento/vpla_ref_23.cm.xml`
- Descarga GeoPackage por capa desde catálogo IDEM

### Estrategia geometría para adapter

1. Semillas de polígonos desde WFS refundido (`VPLA_V_AMBITO_REF_23`, `VPLA_V_ORDENANZA_REF_23`).
2. Enriquecer proyectos del tablón Joomla cuando el título mencione `UE-1`, `CASCO ANTIGUO` u otros códigos SIT.
3. No hay geometría por expediente/licencia individual en portales municipales.

## Datos scrapeables de forma determinista

| Fuente | Campos extraíbles | Mecanismo |
|--------|-------------------|-----------|
| Tablón RSS | `title`, `link`, `pubDate`, `description` (HTML con URLs de PDF/imagen) | Feed XML estable |
| Tablón HTML | título, slug, fecha artículo, enlaces PDF en `/images/ciudadanos/tablonmunicipal/` | Paginación `?start=N` (20/página) |
| Ordenanzas Joomla | título, slug, PDF embebido (dearflip; URL a veces en JS) | Listado + artículo individual |
| Sede board | documento, expediente, procedimiento, categoría, descripción, fecha | Tabla HTML (actualmente vacía) |
| Sede catálogo | nombre trámite, UUID, texto normativo | `/dossier.0` + `/catalog/t/{uuid}` |
| SIT WFS | `DS_NOMB_AMB`, `DS_NOMB_ORD`, `DS_NOMB_RED`, geometría GeoJSON | WFS 2.0 JSON, `CQL_FILTER` por `CD_MUNICIPIO` |
| Formularios PDF | metadatos de trámite (no concesiones) | URLs estáticas conocidas |

**No scrapeable sin autenticación:** `/expedientes`, solicitudes en borrador, buzón electrónico.

## Limitaciones

- Dominio `horcajodelasierra.es` inactivo; usar `horcajodelasierra-aoslos.es`.
- Municipio unificado; el nombre oficial en SIT incluye «-AOSLOS».
- Tablón sede espublico vacío; la publicidad efectiva está en tablón Joomla.
- Licencias: solo formularios y trámites informativos; sin dataset de concesiones.
- Expedientes individuales no publicados; PDFs del tablón sin georreferenciación.
- Capa vigente `VPLA_V_AMBITO` sin features; geometría solo en capas refundidas SIT.
- Sede `/dossier` redirige a `/dossier.0` (302); requiere cookie de sesión para contenido completo.
- URLs Wicket de sede llevan tokens `?x=…` no estables entre sesiones (evitar hardcodear).
- Transparencia urbanismo: 0 documentos.
- No hay sección «bandos de alcaldía» dedicada (solo artículos sueltos en tablón).

## Estrategia adapter recomendada

Patrón similar a `braojos_de_la_sierra.py` / `buitrago_del_lozoya.py`:

1. **Proyectos:** parsear RSS + crawl paginado del tablón municipal Joomla; filtrar con regex urbanística
   (`infracci[oó]n urban`, `licencia`, `planeam`, `PGOU`, `ordenanza`, `UE-\d+`, etc.).
2. **Licencias:** mismas fuentes tablón; añadir semillas estáticas de formularios/trámites sede como
   `tipo=informativo` (opcional, baja prioridad).
3. **PDFs:** extraer de `description` RSS y de artículos (`/images/ciudadanos/tablonmunicipal/*.pdf`).
4. **Geometría:** WFS refundido SIT (`CD_MUNICIPIO=070`); matcher por código de ámbito en título.
5. **Sede board:** poll tabla espublico cuando tenga filas (regex de filas `<tr>` como en Braojos).
6. **Exclusiones:** empleo, sanidad, fiestas, emergencias, residuos, subvenciones no urbanísticas.
7. **IDs:** `horcajo-de-la-sierra-{lic|proy}-{sha256[:14]}`.
8. **BOCM:** mantener como fuente regional complementaria (`boletin_source_id: bocm` en queue).

### Constantes sugeridas

```python
JOOMLA_BASE = "https://www.horcajodelasierra-aoslos.es"
SEDE_BASE = "https://horcajodelasierra-aoslos.sedelectronica.es"
MUNICIPIO = "Horcajo de la Sierra-Aoslos"
WFS_MUNICIPIO_CODE = "070"
SIT_DS_MUNICIPIO = "HORCAJO DE LA SIERRA-AOSLOS"
TABLON_RSS = f"{JOOMLA_BASE}/ciudadanos/tablon-municipal?format=feed&type=rss"
DOSSIER_URL = f"{SEDE_BASE}/dossier.0"
BOARD_URL = f"{SEDE_BASE}/board"
VISOR_URL = "http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=070"
```
