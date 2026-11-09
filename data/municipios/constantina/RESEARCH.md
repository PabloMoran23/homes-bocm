# Constantina — Sevilla — INE 41033

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales y selección

La entrada [PBOM del Ayuntamiento](https://www.constantina.org/es/ayuntamiento/pgou)
redirige mediante HTTP al [portal del PBOM](https://constantina.nuevoplan.es/).
Se verificó esta cadena en la ejecución del adaptador, así como el enlace de ese
portal a su [inventario DOCUMENTOS](https://constantina.nuevoplan.es/documentos/).
La procedencia municipal del dominio del equipo redactor se sustenta en esa
redirección municipal, no únicamente en el nombre del dominio. La
[noticia municipal de inicio de redacción](https://www.constantina.org/es/actualidad/noticias/ARRANCA-LA-ELABORACION-DEL-PLAN-BASICO-DE-ORDENACION-MUNICIPAL-PBOM-DE-CONSTANTINA/)
identifica el instrumento y al equipo Buró4. Esa noticia no genera otro proyecto.

El inventario DOCUMENTOS sirve ocho enlaces PDF en una única página HTML, bajo
las fases 1, 2 y 3. Dos archivos corresponden a fase 1, uno al diagnóstico previo
de fase 2 alojado en constantina.org, y cinco a fase 3 (memoria, planos, DIE,
resumen ejecutivo y salud). Todos pertenecen al mismo PBOM: se devuelve **un
registro con ocho documentos**, sin convertir capítulos, mapas o participación
en actuaciones independientes. Los enlaces gráficos carecen de texto y de alt;
en esos casos se conserva el nombre literal del archivo como título documental.
Los archivos se descubren en el HTML; no hay un catálogo de registros precargado.

No se observó paginación en este inventario. El parser rechaza enlaces de
paginación si aparecen, para exigir revisión en lugar de devolver una primera
página incompleta. La actualización vuelve a leer el inventario entero y
sustituye el fichero de salida solo tras una extracción válida.

## Otros inventarios examinados y límites

El [indicador municipal de modificaciones del PGOU](https://transparencia.constantina.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00010)
respondió HTTP 200 y conserva documentación del PGOU provisional 2. Sus galerías
de catálogo, planos y estudios tienen paginaciones independientes. **Este archivo
histórico queda fuera del adaptador**, no se exporta su primera página como
inventario completo ni se mezcla con el PBOM. La captura inicial se conserva
como evidencia de investigación, no como evidencia de cobertura de esas galerías.

La [resolución BOJA 2021/37/46](https://www.juntadeandalucia.es/boja/2021/37/46)
publica la denegación de aprobación definitiva de aquel PGOU: acuerdo de
01/02/2021, resolución de 16/02/2021 y boletín de 24/02/2021 son eventos distintos.
Por ello la etiqueta genérica del indicador de transparencia no demuestra
aprobación definitiva ni vigencia del PGOU. Esta resolución es contexto para
delimitar fuentes, no un acuerdo relativo al nuevo PBOM ni un registro añadido.

La portada del PBOM incluye enlaces copiados que conducen a Los Molares; quedan
excluidos por dominio e identificación del archivo. Solo se importan documentos
del inventario DOCUMENTOS con código de plan P07 o un PDF municipal identificado
como PBOM de Constantina. Formularios, cuestionarios, navegación y noticias no
son registros. La presencia de formularios de licencia no prueba concesiones;
licencias permanece desactivado y sus métodos rechazan la ejecución explícita.

Cobertura municipal **parcial**: exclusivamente este inventario del nuevo PBOM,
sin pretensión de cubrir otros instrumentos, obras o licencias. No se extraen
fechas del CMS ni de carpetas de subida. `DEF` en un nombre de archivo no acredita
aprobación. Las fechas de publicación, acuerdo y aprobación permanecen nulas;
la etapa literal de la portada se registra con su propia procedencia y no como
fase jurídica. Sin geometría verificada, coordenadas nulas y
`publication_ready: false`. El manifest desactiva programación y jitter.

## Validación reproducida

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_constantina -v`: **8 tests correctos**.
Comprueban agrupación, identidad estable, documentos duplicados, contaminación
de otro municipio, formularios, rechazo de página vacía o cambiada, paginación,
fechas/geometría ausentes, manifest, actualización completa y conservación de la
salida previa ante un fallo.

Extracción real con `ConstantinaAyuntamientoAdapter.backfill_proyectos`, cargando
el manifest y configurando únicamente `capture_dir: evidence` para las capturas.
Resultado: **1 registro, 8 enlaces documentales** en `evidence/proyectos.jsonl`.
`evidence/validation.json` contiene recuentos, URLs consultadas y limitaciones.
`municipal-entry.html` y `documents.html` capturan las respuestas usadas por el
adaptador. `inventory.html`, `pbom.html`, `pbom-docs.html` y
`pgou-boja-2021.html` son capturas de investigación.

Se descargó además el
[resumen ejecutivo](https://constantina.nuevoplan.es/wp-content/uploads/2026/05/P07-F3_EJECUTIVO_DEF.pdf):
HTTP 200, `application/pdf`, firma `%PDF-`, 1.128.913 bytes. Está guardado como
`evidence/pbom-resumen-ejecutivo.pdf`, con metadatos en `document-check.json`.
Esto verifica una descarga documental real; no equivale a auditar todos los PDF
ni a extraer sus geometrías o acreditar vigencia jurídica.

La evidencia es local y no forma parte de los cuatro archivos fuente entregables.
No se ejecutó publicación, geocodificación, sincronización ni acceso a bases de datos.
