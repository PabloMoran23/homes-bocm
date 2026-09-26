# Aldeavieja de Tormes — investigación portal ayuntamiento

**Municipio:** Aldeavieja de Tormes (Salamanca, Castilla y León)  
**Código INE:** 37024  
**Fecha:** 2026-09-05  
**BOCYL (referencia):** 1 aviso

## Resumen

Aldeavieja de Tormes publica trámites y tablón en la **sede electrónica espublico gestiona**
(`aldeaviejadetormes.sedelectronica.es`). El planeamiento aprobado está en el archivo PLAU de la
Junta de Castilla y León (código municipio **024**) y en la Diputación de Salamanca
(`codMunicipio=24`). La geometría de sectores y planes parciales está en el WFS de IDECyL.

La web corporativa `http://aytoaldeaviejadetormes.es` solo muestra datos de contacto; no hay
sección de urbanismo propia.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://aldeaviejadetormes.sedelectronica.es/board` | HTML Wicket | Edictos (vacío sep 2026) |
| Catálogo trámites | `https://aldeaviejadetormes.sedelectronica.es/dossier.0` | HTML Wicket | ~114 trámites (urbanismo/licencias) |
| PLAI info pública | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=024` | HTML | Sin documentos en trámite (sep 2026) |
| PLAU archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=024` | HTML | 4 instrumentos aprobados |
| Diputación Salamanca | `http://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=24&funcion=VerNormasUrbanisticas&nombre=Aldeavieja+de+Tormes&prestacion=NormasUrbanisticas` | HTML OpenCMS | Normas urbanísticas, plan parcial R-2, modificación nº1 NUM |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, plan parcial UBZ-I2, NUM |
| Web municipal | `http://aytoaldeaviejadetormes.es` | HTML estático | Solo contacto |

## Tablón de anuncios (`/board`)

Tabla HTML Wicket estándar espublico. En septiembre 2026 **no hay anuncios publicados**
(«No se han encontrado elementos»). Cuando haya edictos, enlaces `preview-document/{uuid}`.

## Planeamiento (PLAU JCyL, municipio 024)

Documentos aprobados indexados:

| Fecha | Título |
|-------|--------|
| 13/01/2011 | NORMAS URBANÍSTICAS MUNICIPALES |
| 06/05/2016 | CORRECCIÓN DE ERRORES DE LAS NUM (parámetro suelo rústico) |
| 01/08/2019 | PLAN PARCIAL DEL SECTOR URBANIZABLE INDUSTRIAL UBZ-I2 |
| 23/02/2024 | MODIFICACIÓN Nº 1 DE LAS NUM (reconocimiento suelo urbano 1857 m²) |

Diputación de Salamanca refleja además aprobación plan parcial sector **R-2** (2012) y
modificación puntual nº 1 NUM (2023).

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas (UUIDs estándar espublico):

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Solicitud de Licencia de Ocupación
- Modificación del Planeamiento de Desarrollo / Planeamiento General
- Solicitud de Actuación Urbanística, Certificado o Informe Urbanístico
- Solicitud de Declaración de Ruina

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones.

- Tablón vacío en la fecha de investigación.
- Páginas de trámite del catálogo sede como referencia informativa.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 5 sectores (UBZ I1/I2, UBZ R1/R2, UNC R1)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial (UBZ-I2)
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (NUM)
  - Filtro: `CQL_FILTER=n_mun = 'Aldeavieja de Tormes'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer documentos PLAU por código
  de sector (p. ej. UBZ-I2) en título
- **Limitaciones:** tablón sin anuncios; licencias sin geometría enlazable; no hay visor ArcGIS
  municipal; sede requiere `insecure_ssl` (certificado Firmaprofesional); `/dossier.0` requiere
  cookie de sesión previa en `/board`

## Limitaciones

- Tablón vacío: sin licencias ni edictos recientes scrapeables.
- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0`; catálogo requiere bootstrap de sesión en `/board`.
- Web municipal sin contenido urbanístico.

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tablón `/board` + extracto `/info.0` (cuando haya anuncios).
3. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
4. Parseo tabla PLAU Junta CYL (provincia 37, municipio **024**).
5. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
6. Semillas Diputación Salamanca + URLs PLAI/PLAU.
7. IDs estables: `aldeavieja-de-tormes-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Mismo patrón CYL/Salamanca: `alba_de_tormes.py`, `valverdon.py`
- Sede espublico + SSL: `pelabravo.py`
- IDECyL WFS partial: `villadangos_del_paramo.py`
