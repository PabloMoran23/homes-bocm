# Pizarra — Málaga — INE 29080

Investigación y extracción real: 7 de noviembre de 2026 (UTC). Adaptador único:
`municipio.adapters.pizarra:PizarraAyuntamientoAdapter`.

## Descubrimiento de fuentes oficiales actuales

La [web municipal](https://www.pizarra.es/) mantiene enlaces de PGOU y
Transparencia a [la entidad provincial ent-807](https://www.malaga.es/gobiernoabierto/portal/entidad/ent-807/pizarra).
Ese destino devolvió HTTP 202 con cuerpo vacío en las consultas realizadas,
incluidas variantes con barra final y sin www. No se ha sustituido por una
noticia que mencione el PGOU ni se ha convertido ese enlace genérico en proyecto.
La portada conserva además un enlace de delimitación de hábitats rurales con
`href="#"`, que no proporciona documentos utilizables.

La [nueva sede](https://sede.malaga.es/pizarra) ofrece un
[portal de transparencia](https://sede.malaga.es/pizarra/portal-de-transparencia/)
que remite al mismo destino provincial. Su
[tablón público](https://sede.malaga.es/pizarra/tablon-de-anuncios/) mostraba
cuatro anuncios sobre personal, padrones tributarios y ayudas LEADER, sin
instrumentos urbanísticos ni obras concretas extraíbles. La antigua sede
`https://pizarra.sedelectronica.es/transparency/` informa que la página está
deshabilitada. Los formularios, anuncios tributarios y convocatorias se excluyen.

Fuente operativa: [Publicación de resoluciones ambientales de instrumentos de
planeamiento urbanístico — Junta de Andalucía](https://www.juntadeandalucia.es/medioambiente/daepu/).
Su formulario público GET admite `find=findResolucionesFiltered` y
`filter5=PIZARRA` (Municipio). Se consulta el [inventario municipal filtrado](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/find?find=findResolucionesFiltered&filter5=PIZARRA).
Cada fila se verifica contra municipio PIZARRA y provincia MÁLAGA; cada ficha
debe repetir expediente, actuación y municipio/provincia.

## Resultado real y unidad de extracción

El inventario actual devuelve **Página 1 de 1**, tres expedientes y seis documentos:

| Expediente | Instrumento identificado por la actuación oficial | Ficha | Documentos asociados |
| --- | --- | --- | --- |
| EA/MA/54/18 | Plan parcial SURs-PZ.01 Casablanca del PGOU de Pizarra | [13641](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/13641) | Admisión/inadmisión 09/04/2019; informe ambiental estratégico 24/02/2020; publicación BOJA 04/03/2020 |
| EA/MA/052/19 | Modificación de categoría en franja de suelo no urbanizable | [17740](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/17740) | Admisión/inadmisión 20/11/2019; documento de alcance 07/04/2021 |
| EA/MA/24/22 | Modificación de los artículos 101 y 121 del PGOU | [38840](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/38840) | Documento de alcance 17/04/2023 |

No son expedientes precargados: el adaptador descubre las filas actuales y sus
fichas, extrae todos los documentos de cada ficha y agrupa por número de
expediente. El título conserva literalmente la actuación publicada, aunque
comience por «Resolución» o «Documento de alcance». Cada documento conserva su
URL, tipo, fecha y ficha de procedencia. Los identificadores del registro son
estables por expediente. Se eliminan de las URL los tokens públicos de sesión
`jsessionid`, sin almacenarlos como identificadores.

El adaptador comprueba el contador de paginación y recorre todas las páginas,
manteniendo el filtro municipal explícito en cada solicitud. No utiliza un
límite de páginas ni de registros. Contadores ausentes, páginas repetidas o
inconsistentes, cambios de columnas, errores HTTP, fichas sin documentos o
identidades contradictorias abortan la extracción antes de sustituir la salida.
La actualización vuelve a extraer una instantánea completa.

## Fechas, procedencia y límites

Fuente autonómica oficial alternativa; `proyectos.source: ayuntamiento` es el
selector del pipeline para cargar el adaptador de portal (el esquema existente
solo contempla ese selector o el BOCM legacy). En los registros la procedencia
real es `source: junta_de_andalucia`, `origen: daepu`.

La fecha de la ficha se conserva como `fecha_resolucion_ficha` en
`fichas_fuente`. La tabla documental denomina toda su columna «Fecha de
Resolución», incluso para publicaciones BOJA: se conserva literalmente como
`fecha_resolucion_fuente`. Para BOJA se etiqueta además `fecha_publicacion`;
para los demás documentos, `fecha_resolucion`. Las fechas documentales se
mantienen en cada documento, sin elegir arbitrariamente una fecha única del
instrumento. `fecha_acuerdo`, `fecha_aprob` y `fecha_publicacion` del registro
quedan nulas. No se deduce aprobación urbanística de una resolución ambiental
ni se utiliza el tipo documental como fase del instrumento.

Cobertura parcial: solo expedientes del inventario ambiental cuyo municipio
principal sea Pizarra; no se consulta el campo «Otros Municipios». No es el
inventario completo del PGOU, sus modificaciones, licencias o todas las obras
públicas. No se afirma que las tres actuaciones estén actualmente aprobadas,
vigentes, ejecutadas ni que sus trámites sean los últimos existentes fuera de
este inventario. No se incluyen concesiones de licencias: no se ha verificado
un registro público apropiado. `licencias.enabled=false`,
`schedule.enabled=false`, `geocode.jitter_missing=false`. No hay coordenadas ni
geometrías verificadas; los registros tienen `publication_ready=false`.

## Validación reproducible y evidencia local

Runtime requerido:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: ejecutar ese runtime con `-m unittest municipio.test_pizarra -v`.
**9 pruebas correctas**: identidad del manifest, filtro municipal, rechazo de
fuentes vacías/incorrectas, paginación completa, repetición de página sin
sobrescritura, agrupación documental, separación de fechas y licencias
desactivadas. Los fixtures de las pruebas son sintéticos y están declarados
como tales; no alimentan la extracción real.

Extracción real realizada cargando `load_manifest('pizarra')`, instanciando el
adaptador indicado y llamando a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`
con `config={'capture_dir': 'evidence'}`. Resultado: **3 registros, una página,
6 documentos asociados**. `evidence/validation.json` contiene `live_records`,
`source_urls`, limitaciones, instante UTC y comprobaciones HTTP de documentos.
Las seis URL de descarga devolvieron HTTP 200 y firma `%PDF-`; el servidor las
sirve como `application/octet-stream;charset=UTF-8`. Solo se capturaron los
primeros 1024 bytes de cada PDF (`*.pdf.head`), sin afirmar lectura completa ni
validación del contenido jurídico de los PDF. Las fichas y el inventario se
capturan completos como `daepu-*.html`; las otras consultas exploratorias
también quedan en `evidence/`. La evidencia es local y no se añade al código.

No se ejecutaron publicación, base de datos, geocodificación ni pipeline global.
