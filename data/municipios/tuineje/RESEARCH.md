# Tuineje — INE 35030, Las Palmas, Canarias

Investigación y extracción real: 7 de noviembre de 2026. Se revisaron el contrato
`municipio/adapters/portal.py`, el cargador y esquema de `municipio/manifest.py`,
el registro y los ejemplos Chipiona y Manlleu antes de implementar.

## Fuentes oficiales descubiertas

- [Portal municipal de transparencia: información del planeamiento](https://transparencia.tuineje.es/es/informacion-del-plan-insular-o-general-de-ordenacion-y-de-los-planes-y-proyectos-de-desarrollo-del).
  En la consulta observada indica «Última actualización: 08/06/2026». Esta es una
  fecha del contenido web, no una fecha de publicación de cada instrumento ni de
  aprobación. Enlaza Normas Subsidiarias en Sereta, cartografía GrafCan y el
  archivo urbanístico del Gobierno de Canarias. Sereta agotó el tiempo de espera
  del navegador de investigación; no se utiliza como fuente de registros.
- [Archivo de planeamiento: municipio Tuineje](https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=30&provincia=35).
  Identifica TUINEJE, provincia 35, municipio 30. Inventario observado:
  planeamiento general 14, desarrollo 1, catálogos 0, ordenanzas 0,
  proyectos de urbanización 0, proyectos de ejecución de sistemas 0.
- [Planeamiento general](https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/urbanisticaPlaneamientoGeneral.jsp)
  y [planeamiento de desarrollo](https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/urbanisticaPlaneamientoDesarrollo.jsp).
  Requieren visitar primero el inventario municipal en la misma sesión pública.
  Una petición aislada puede devolver cero resultados por pérdida del contexto.
  Visitar la categoría establece también el contexto necesario para sus fichas.
  No se utiliza autenticación ni credenciales.

## Extracción y semántica

Se extraen **15 expedientes reales**, identificados por su referencia oficial:
14 de planeamiento general (NNSS de 1988/0115 y modificaciones/revisión parcial)
y la modificación del Plan Parcial Valle del Aceitún 2005/0033. Cada ficha se
consulta y valida contra el expediente y título del listado. No se generan
registros de navegación, formularios, noticias ni anuncios de contratación.

**129 enlaces documentales** quedan agrupados en `documentos`, conservando
identificador, título original, URL oficial ShowPdfServlet, ficha de procedencia
y fecha de aprobación documental. Por ejemplo, NNSS 1988/0115 reúne normativa
y 49 planos, incluyendo versiones explícitamente marcadas ANULADO y modificaciones.
Estas etiquetas se conservan: un documento archivado o la situación Disponible
no demuestra vigencia jurídica. Un mismo plano puede constar en el instrumento
base y en una modificación; se respeta esa pertenencia sin crear proyectos por PDF.

Las columnas Fecha aprobación, Fecha BOC y Fecha normativa se mantienen separadas.
`fecha_publicacion` procede de Fecha BOC; `fecha_aprobacion_catalogo` conserva la
fecha original de catálogo. `fecha_aprob` usa esa columna salvo que los comentarios
la cualifiquen. El caso 2005/0033 dice expresamente que 10/10/2005 corresponde a
asunción por COTMAC y que el Ayuntamiento aprobó definitivamente el 14/11/2005:
la fecha normalizada de aprobación es 2005-11-14 y ambas afirmaciones quedan
trazadas. Se conserva el comentario completo. No se deducen fechas de acuerdo,
fases, ejecución ni coordenadas. `publication_ready: false`; sin geometría.

Los listados observados sirven todos sus expedientes en una página. Los planos
de NNSS también aparecen completos. El parser exige coincidencia entre el total
municipal, total de categoría y número de expedientes únicos; en cada ficha
comprueba el total de las cinco categorías documentales. Si aparece paginación
que reduzca los elementos servidos, falla explícitamente sin escribir un resultado
truncado. Actualización y backfill producen una instantánea completa de estas dos
categorías, sin cortar por fecha ni conservar un cursor que omita cambios.

## Cobertura y límites

Es un inventario oficial consultado actualmente con expedientes históricos,
no un registro exhaustivo de actuaciones recientes. Solo cubre las dos categorías
urbanísticas indicadas; no cubre toda la obra pública municipal ni nuevas actuaciones
que no hayan llegado al archivo regional. No se verifica la vigencia legal de cada
instrumento ni se extrae contenido o geometría de los PDFs. No hay registro público
de concesiones de licencia verificado: `licencias.enabled: false`. También quedan
desactivados `schedule.enabled` y `geocode.jitter_missing`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_tuineje -v`: **8 pruebas correctas**.
Comprueban agrupación y aislamiento documental, semántica de fechas cualificadas,
rechazo de fuentes erróneas/formularios, recuentos incompletos, manifiesto,
licencias desactivadas y actualización como instantánea.

Extracción real ejecutada con `load_manifest('tuineje')`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `portal.config.capture_dir` dirigido a `evidence/captures` solo en la ejecución.
Resultado: **15 registros, 129 documentos**, política compartida sin entidades
desconocidas. No hay cambios en código compartido ni dependencias.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (recuento, URLs consultadas y limitaciones),
`evidence/captures/*.html` (portal, inventario, dos listados y 15 fichas),
`evidence/parser-tests.txt` y comprobación de muestra documental en
`evidence/document-check.json`. No se ejecutaron publicación, sincronización,
geocodificación ni operaciones de base de datos.
