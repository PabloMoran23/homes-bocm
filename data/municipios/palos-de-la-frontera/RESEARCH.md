# Palos de la Frontera — Huelva — INE 21055

Investigación y extracción en vivo: 7 de noviembre de 2026. Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos Chipiona y Hernani. Solo se añaden los cuatro archivos específicos solicitados; la evidencia queda fuera de los fuentes.

## Fuentes y alcance

La portada oficial https://palosfrontera.com/ responde correctamente, pero su navegación observada no ofrece un inventario de planeamiento. No se utilizan noticias, formularios, contratos ni la sede de la mancomunidad Moguer-Palos como sustitutos de instrumentos urbanísticos.

Se usa el inventario público oficial de la Junta de Andalucía de resoluciones de evaluación ambiental estratégica de instrumentos de planeamiento urbanístico (DAEPU): https://www.juntadeandalucia.es/medioambiente/daepu/ . Consulta reproducible:

https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/find?find=findResolucionesFiltered&filter3=HUELVA&filter5=PALOS+DE+LA+FRONTERA&size=10&page=1

Esta consulta devuelve **cinco expedientes ambientales**, agrupados en **cuatro instrumentos**, con **seis documentos**:

| Instrumento identificado en la fuente | Expedientes y fichas | Documentación observada |
| --- | --- | --- |
| Innovación de planeamiento nº 3 del PGOUA, parcela en calle Gran Almirante Cristóbal Colón, Mazagón | [IAE/HU/008/20](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/31602), [IAE/HU/002/21](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/27360) | Inadmisión de 14/12/2020, informe ambiental de 18/05/2021 y publicación BOJA de 24/05/2021 |
| PGOU del municipio | [EAPU/HU/019/11](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/24844) | Archivo del procedimiento ambiental de 10/02/2021 |
| Modificación nº 2 del Plan General adaptado parcialmente a la LOUA | [EAPU/HU/013/14](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/24881) | Archivo del procedimiento ambiental de 10/02/2021 |
| Plan Especial de Protección del Casco Histórico | [IAE/HU/010/26](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/54463) | Categoría del portal «Admisión/ Inadmisión Trámite», resolución de 13/07/2026 |

Los PDF de los dos expedientes de innovación identifican expresamente la misma innovación nº 3 del PGOUA. Se agrupan por esa denominación numerada; los demás instrumentos se agrupan por expediente. El primer título literal y su expediente se conservan como referencia principal, sin presentarlos como estado actual; `resoluciones` conserva todos los títulos, fechas, expedientes, URLs y la consulta de origen. `expedientes` contiene todas las referencias del grupo y `documentos` todos los enlaces asociados con su ficha de procedencia. Los identificadores de sesión se eliminan de las URLs; no se fijan listas de registros o URLs de expedientes dentro del scraper.

La lectura del PDF del Plan Especial confirma admisión a trámite ambiental. El scraper conserva la categoría más amplia del inventario y no interpreta el PDF como aprobación del plan. Los PDF de inadmisión e informe ambiental de la innovación también se inspeccionaron como texto; las transcripciones están en la evidencia.

## Semántica y limitaciones

Cobertura parcial: instrumentos que aparecen en DAEPU con municipio principal exactamente Palos de la Frontera y provincia Huelva. No incluye menciones solo en «Otros Municipios», todo el planeamiento municipal, proyectos no sujetos a ese registro, obras municipales ni un histórico completo de licencias. La disponibilidad actual de una ficha no acredita vigencia del instrumento ni actividad de obra. Los archivos y la inadmisión son eventos ambientales reales asociados a instrumentos, no aprobaciones ni licencias concedidas.

`fecha_resolucion` pertenece al evento/documento ambiental. `fecha_publicacion` solo se utiliza para el documento identificado por el registro como publicación BOJA. No se inventan fechas de acuerdos municipales, aprobaciones, fases, coordenadas ni geometrías. Se declara `publication_ready: false` y `geometry_status: unavailable`. Las licencias, programación y jitter geográfico están desactivados en el manifest.

El esquema compartido admite `proyectos.source: ayuntamiento` como ruta del adaptador de portal (frente a la ruta BOCM heredada). Aquí la fuente material es autonómica: `portal.base_url`, notas del manifest y `source: junta_de_andalucia` en los registros la identifican explícitamente.

## Paginación, cambios y fallos

El pie vivo informa «Página 1 de 1». El adaptador recorre todas las páginas declaradas manteniendo los filtros, sin un máximo que corte resultados. Comprueba página recibida, estabilidad del total, duplicados, municipio/provincia exactos, identidad ficha/inventario y existencia de documentos. Un vacío o cambio incompatible provoca error antes de reemplazar el archivo anterior. Las actualizaciones refrescan el inventario completo; no mantienen un log incremental ni afirman detectar borrados históricos. No se interpreta la ausencia de un resultado como derogación.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_palos_de_la_frontera -v
```

Siete tests correctos: identidad municipal y provincial, fechas documentales separadas, documentos y procedencia, agrupación, rechazo de formularios/vacíos, paginación de varias páginas y protección del archivo anterior ante respuestas repetidas, manifest y licencias desactivadas. Los tests no necesitan red ni evidencia local.

Extracción real mediante `load_manifest('palos-de-la-frontera')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando únicamente `portal.config.evidence_dir` para guardar capturas. Resultado: **4 registros, 5 expedientes, 1 página**, política compartida con cero registros desconocidos. No se ejecutaron otras etapas, publicación ni geocodificación.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, inventario filtrado y las cinco fichas HTML, seis PDF completos y tres transcripciones de comprobación. Los seis enlaces documentales devolvieron HTTP 200 y firma `%PDF-`; el servidor declara `application/octet-stream;charset=UTF-8`. `validation.json` conserva URL de origen/final, tamaño y captura de cada documento, fuente consultada, conteo real y limitaciones. La evidencia no se añade a Git.
