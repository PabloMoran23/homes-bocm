# Vilamarxant — INE 46256, Valencia

Investigación y extracción real: 2026-11-07. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y alcance

El adaptador extrae **un instrumento de planificación municipal real**, el Plan
Local de Prevención de Incendios Forestales (PLPIF), desde el Sistema Integrado
de Gestión de Incendios Forestales de la Generalitat Valenciana (SIGIF):

- [Ficha municipal](https://prevencionincendiosgva.es/Planificacion/DetallePlanesMunicipio/532).
  Su tabla `tablaMunicipio` identifica expresamente Vilamarxant, 46256 y Valencia.
- [Inventario de PLPIF](https://prevencionincendiosgva.es/Planificacion/PLPIFList).
  La fila de Vilamarxant en `tablaValencia` aporta estado, resolución, fecha de
  resolución, fecha DOGV y texto de vigencia. Se cruza su identidad documental
  con la ficha municipal.
- [Plan completo](https://prevencionincendiosgva.es/Documents/planes_PLPIF/46/PLPIF462567.zip).
  Descarga verificada HTTP 200, 74.832.190 bytes. Contiene
  `VILAMARXANT/PLPIF_VILAMARXANT_v_final.pdf` y
  `VILAMARXANT/2020_10407.pdf`. El PDF del plan se identifica en portada y su
  índice incluye propuestas sobre red viaria, áreas cortafuegos y red hídrica,
  junto con programación temporal y económica. Es un plan territorial de
  prevención; no se presenta como PGOU, licencia ni obra ejecutada.
- [Resolución 2020/10407](https://dogv.gva.es/datos/2020/12/09/pdf/2020_10407.pdf).
  HTTP 200 y firma PDF verificados; texto inspeccionado con `pdftotext`.
- [Informe anual 2023 enlazado en la ficha](https://prevencionincendiosgva.es/Documents/planes_PLPIF/46/PLPIF462567/PLPIF462567_2023.zip).
  Se conserva como documento del mismo plan; no se descargó ni interpretó su
  contenido. Su año no se convierte en fecha de aprobación o ejecución.

La identificación institucional del dominio se corrobora en la
[sede de la Generalitat](https://sede.gva.es/es/detall-tramit?id_proc=20876),
que enlaza `prevencionincendiosgva.es`, y en el pie institucional del SIGIF.
El dominio `desarrollo.vaersa.org` permitió descubrir la misma ficha, pero su
ZIP devolvió 404. Se utiliza el dominio público actual anterior, donde el ZIP
sí respondió 200; no se emplea una copia de desarrollo como fuente operativa.

## Descubrimiento y exclusiones

La web `https://www.vilamarxant.es` cerró la conexión sin respuesta en la
consulta directa. La sede
[Urbanismo](https://vilamarxant.sede.dival.es/catalogoservicios.aspx?ambito=1&area=1875)
publica solicitudes y declaraciones responsables: no demuestra concesiones.
Licencias quedan desactivadas.

El [portal municipal de transparencia](https://vilamarxant.governalia.es/es/)
expone categorías de texto/planimetría, modificaciones e infraestructuras.
Se siguieron los scripts públicos del visor para consultar las categorías
`11.03`, `11.04`, `11.05` y `01.03.06` de la entidad pública `63100`, mediante
`https://app.governalia.es/gvn/rest/transparency/document/dt-bm25` en sesión
anónima inicializada con su visor. Las respuestas observadas dieron
`recordsTotal=0`, `recordsFiltered=0`. Esto limita esta consulta; no prueba
que el ayuntamiento carezca de otros expedientes.

No se extraen noticias, anuncios de contratación, formularios ni planes
supramunicipales (Turia y demarcación Llíria) enlazados en la ficha. El Plan
Local de Quemas y la fila LOTUP pendiente quedan fuera del alcance específico
del adaptador. No se pretende cubrir todo el planeamiento ni toda la obra
pública municipal. La cobertura es explícitamente `municipal_plpif_only`.

## Semántica, documentos y paginación

La fecha **2020-11-24** es la resolución autonómica de aprobación; la fecha
**2020-12-09** es su publicación en DOGV. Ambas se extraen de columnas distintas
del inventario. El PDF también menciona acuerdo plenario de 03/11/2020, pero el
adaptador no analiza el PDF y deja `fecha_acuerdo=null`. No mezcla esa fecha
con la resolución ni con la publicación. Se retiene el texto de vigencia sin
calcular una fecha final o presumir cumplimiento de revisiones parciales.

Los tres documentos observados se agrupan en un único registro. El scraper
recoge todos los enlaces del renglón PLPIF, incluidos todos los informes
anuales, y falla si falta el plan o si las identidades documentales divergen.
Los documentos tienen rol y URL de la ficha de procedencia. El registro
identifica a la Generalitat como fuente, aunque `proyectos.source=ayuntamiento`
se conserva por el contrato de selección municipal del manifiesto.

El listado completo sirve todas las filas por provincias en HTML. DataTables
muestra cinco filas por página mediante paginación cliente, sin `serverSide`
ni petición de datos remotos. El parser recorre todas las filas de Valencia,
no solo las visibles en la primera página. La ficha municipal tiene un único
renglón PLPIF. Si aparecen enlaces de paginación o `serverSide: true`, se falla
para exigir revisión en vez de generar una extracción recortada. Si aparece
más de un plan municipal se exige revisar su agrupación, sin escoger uno
silenciosamente. `update_proyectos` refresca la instantánea completa.

Sin coordenadas ni geometría extraídas: `publication_ready=false`,
`geometry_status=unavailable`, `lat/lon/geometry=null`. La cartografía existe
en el plan, pero no se ha digitalizado ni validado una geometría por actuación.
El guard compartido de entidades marca este tipo especializado como pendiente
por identidad insuficiente para su taxonomía; no se modifica ni elude. No se
infiere actividad elegible, concesión ni ejecución desde la aprobación del plan.

## Validación y evidencia local

Pruebas offline (4 correctas):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_vilamarxant -v
```

Cubren agrupación de todos los anexos, aislamiento de documentos regionales y
formularios, fechas diferenciadas, identidad INE/provincia, cambios de esquema,
ausencia de documentos, resolución discordante, origen externo inesperado,
paginación nueva y escritura de una instantánea con licencias desactivadas.

Extracción real realizada cargando `load_manifest('vilamarxant')`,
`load_portal_adapter(manifest)` y `backfill_proyectos` con destino local.
Resultado: **1 registro, 3 enlaces documentales**. No se emplean registros
precargados en producción; las pruebas usan fixtures sintéticos explícitos.

`evidence/proyectos.jsonl` y `evidence/validation.json` contienen el resultado,
recuento real, fuentes y limitaciones. Se guardaron capturas HTML del inventario
y ficha, respuestas de descubrimiento, ZIP completo, PDF del plan, resolución
y sus textos inspeccionados. La evidencia permanece local y no se añade a los
cuatro archivos fuente. No se ejecutó publicación, base de datos ni despliegue.
