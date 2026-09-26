# Espartinas — investigación portal ayuntamiento

Municipio: **Espartinas** (`espartinas`) — Sevilla, Andalucía (INE **41045**, BOJA).

## URLs base y páginas semilla

| Fuente | URL | Rol |
|--------|-----|-----|
| Web corporativa (OpenCMS INPRO theme7) | https://www.espartinas.es/es/ | CMS municipal; tablón enlaza a sede |
| Tablón de anuncios (espublico gestiona) | https://espartinas.sedelectronica.es/board | Anuncios IP, licencias, planeamiento |
| Sede electrónica | https://espartinas.sedelectronica.es/ | Trámites, dossier, consulta expedientes (auth) |
| Urbanismo (trámite sede) | https://espartinas.sedelectronica.es/citizen-service/a5e574c0-654d-4285-8ad3-fc31ba7ad2af | Catálogo trámites urbanismo |
| Transparencia (OpenCMS compartido) | https://transparencia.espartinas.es/es/transparencia/ | Indicadores ITA urbanismo |
| PGOU — indicador 50 | https://transparencia.espartinas.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00039/ | PDFs planos PGOU (Diputación) |
| PGOU PDFs (Dip. Sevilla) | http://multimedia.dipusevilla.es/espartinas/pdfs/pgou/ | Mapas OR/IN escaneados |
| SITUA (Junta Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41045 | Consulta planeamiento digitalizado regional |

## Expedientes / proyectos

- **Tablón espublico gestiona** (`/board`): HTML con filas `<td class="class_*">` (documento, expediente, procedimiento, categoría, descripción, fecha). Enlaces a `/preview-document/{uuid}`.
- Procedimientos urbanísticos observados: *Planeamiento de Desarrollo* (Estudio de Detalle El Jardín I, exp. 105325U), *Licencias de Ocupación*.
- **Transparencia PGOU**: ~17 PDFs de planos (OR-1a…OR-7b, IN-0, etc.) alojados en `multimedia.dipusevilla.es`.
- **SITUA**: visor regional de planeamiento aprobado (PDFs escaneados); no listado de expedientes municipales en curso.
- **Consulta expedientes** (`/expedientes`): requiere identificación; sin listado público.

## Licencias

- Tablón publica edictos de *Licencias de Ocupación* y anuncios relacionados con urbanismo.
- No hay dataset histórico de licencias de obra con coordenadas.
- Trámites de licencia/comunicación previa vía sede (`/dossier`, sección Urbanismo); sin listado abierto.
- Diputación de Sevilla no expone LicytalPub verificable para este ayuntamiento (CIF probado sin registro).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** SITUA (PDF escaneado, sin WFS/ArcGIS queryable); PGOU en PDF raster (Dip. Sevilla); tablón solo documentos PDF.
- **Estrategia:** no hay visor SIG municipal ni WFS enlazable por código de expediente; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** planeamiento solo en PDF; SITUA no expone geometría vectorial por expediente; sede no publica ámbitos georreferenciados.

## Limitaciones generales

- Web OpenCMS sin sección urbanismo dedicada (contenido en transparencia + sede).
- Tablón mezcla anuncios no urbanísticos (RRHH, subvenciones); filtrado por regex en adapter.
- Fechas del tablón incluyen entradas futuras (calendario administrativo).
