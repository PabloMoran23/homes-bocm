# Pontedeume — INE 15069 — A Coruña

Investigación y extracción: 9 de noviembre de 2026. Un adaptador municipal, sin cambios compartidos ni dependencias nuevas.

## Inventarios oficiales examinados

- [Tablón municipal](https://sede.pontedeume.gal/sxc/es/informacion/tablon/index.html): fuente implementada. Expone diez páginas de diez anuncios y advierte que muestra los 100 más recientes. Se recorren todos los enlaces de paginación descubiertos, incluidos los descubiertos en páginas posteriores. Se rechazan páginas repetidas, paginación desconocida y discrepancias con el total anunciado; cualquier límite de seguridad causa error antes de escribir. No se afirma cobertura histórica exhaustiva.
- [Plan Xeral municipal](https://www.pontedeume.gal/o-teu-concello/plan-xeral/): localizado mediante búsqueda oficial; la raíz del dominio municipal respondió HTTP 403 en requests. No se utiliza el texto indexado como registros de extracción.
- [Planes y programas de transparencia](https://sede.pontedeume.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html): inventario localizado que mezcla PXOM, movilidad, prevención de incendios, presupuestos y planes administrativos. No se interpreta cada plan administrativo como proyecto físico ni se incluye en este adaptador.
- [Urbanismo SIOTUGA](https://siotuga.xunta.gal/siotuga/urb): lectura HTTP 200; la fila 15069 identifica Pontedeume y PXOM, con fecha de aprobación 2016-05-27. Su enlace lleva al [inventario por INE](https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15069), que carga los resultados mediante JavaScript. Se conserva como descubrimiento, sin mezclar este PXOM con la modificación extraída ni asumir que ambos son un único expediente. Este inventario regional no está implementado.

## Resultado real y selección

**1 instrumento urbanístico**, expediente **2020/U032/000001**: «PUBLICACIÓN APROBACIÓN DEFINITIVA MODIFICACIÓN PUNTUAL PXOM URDI-2 LEITE CELTA».

[Ficha municipal concreta](https://sede.pontedeume.gal/sxc/es/informacion/tablon/2026/ANUNCIO_PROG_20261103143000093.html). Su artículo contiene literalmente el expediente. Se agrupa por esa referencia, nunca por número de documentos. El registro retiene el título original, la ficha, la página de inventario, cada anuncio con su fecha y todos los enlaces documentales con procedencia. Dos adjuntos:

- [Anuncio DOG adjunto](https://sede.pontedeume.gal/sxc/export/sites/pontedeume/recursos/downloads/Tablon/2026/ANUNCIO_PROG_20261103143000093_ANEXO_1793712600-0.pdf): HTTP 200, application/pdf, firma PDF, 429840 bytes.
- [Justificante de publicación](https://sede.pontedeume.gal/sxc/export/sites/pontedeume/recursos/downloads/Tablon/2026/SELLADO_ANUNCIO_PROG20261103143000.pdf): HTTP 200, application/pdf, firma PDF, 87662 bytes. Se distingue del documento del anuncio; no constituye otro proyecto.

El filtro selecciona títulos explícitos de planeamiento urbano (PXOM, planes generales/parciales/especiales, estudios de detalle, proyectos de urbanización/reparcelación); excluye solicitudes, formularios, contratación, subvenciones y planes de riesgos administrativos. Los candidatos requieren expediente y documento sustantivo en su ficha; si faltan, la extracción falla para revisión. El tablón también contiene concesiones de agua/costas y anuncios de expropiación sin identificación de proyecto en su título: se excluyen conservadoramente. No son licencias de obra concedidas. Tampoco se extraen personal, ordenanzas o el plan de prevención de incendios como actuaciones físicas.

## Fechas y límites semánticos

`fecha_publicacion: 2026-11-03` corresponde exclusivamente al tablón. El título informa de publicación de aprobación definitiva, pero no se convierte esa fecha en fecha del acuerdo. No se extrae el contenido de los PDF ni se inventan `fecha_acuerdo`, `fecha_aprob`, fase, vigencia, ejecución, dirección o coordenadas. `publication_ready: false`, `geometry_status: unavailable`.

La cobertura es parcial: instrumentos explícitos presentes en el listado público actual, no todos los expedientes ni todo el histórico municipal. El refresco incremental vuelve a recorrer el inventario completo porque los anuncios pueden desaparecer del tablón. No conserva un histórico acumulado mediante el fichero de estado. Licencias desactivadas por falta de registro de concesiones verificado. Programación desactivada y geocodificación sin jitter.

## Verificación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `-m unittest municipio.test_pontedeume -v`: **8 pruebas correctas**. Cubren manifest, selección, distinción de fechas, rechazo de formularios/contratación, agrupación y procedencia documental, páginas descubiertas posteriormente, listados repetidos/incompletos, conservación de salida ante error y licencias sin red.

Extracción real invocando `PontedeumeAyuntamientoAdapter('pontedeume', config={'capture_dir': 'evidence/live'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: diez páginas, cien anuncios examinados y un registro escrito. Se comprueban por HTTP los dos PDF adjuntos completos y se guardan sus hashes SHA-256. Evidencia local no destinada al commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML en `evidence/live/` y `evidence/document-1.pdf`, `evidence/document-2.pdf`. La validación contiene URLs, conteo, fecha de comprobación, límites y metadatos de descarga.
