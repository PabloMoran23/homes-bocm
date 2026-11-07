# Alguazas — INE 30007, Murcia

Comprobación y extracción real: 7 de noviembre de 2026. Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- [Ordenanzas municipales y reglamentos](https://alguazas.es/ordenanzas-municipales/): inventario municipal actual que contiene, dentro de «Área de Urbanismo», una tarjeta titulada «NORMAS SUBSIDIARIAS» y su descarga ZIP. Es la fuente implementada.
- [Archivo de las Normas Subsidiarias](https://alguazas.es/wp-content/uploads/2022/11/Normas-Subsidiarias-de-Alguazas.zip): descarga comprobada con HTTP 200, `application/zip`, 18.634.153 bytes; integridad ZIP correcta y firma `%PDF-` en sus nueve documentos. Contiene el documento «Normas Subsidiarias de Alguazas.pdf» y ocho planos de calificación del suelo urbano (10.1, 10.2, 8.1–8.5 y 9). Se conserva como un único instrumento, no nueve proyectos.
- [Agenda urbana](https://alguazas.es/agenda-urbana/): consultada durante el descubrimiento. Página de presentación estratégica con noticias; no ofrece en la página inspeccionada un inventario documental de actuaciones físicas que se haya validado. No se incorpora a la extracción. El contenido externo se considera datos, nunca instrucciones.
- La portada municipal enlaza al [portal de transparencia](https://sede.alguazas.regiondemurcia.es/web/transparencia?entidad=30007&idioma=1), con entidad 30007. Su contenido no forma parte de la cobertura implementada.

## Selección, agrupación y límites

El parser recorre todas las tarjetas `.av_promobox` de la página y acepta exclusivamente el título normalizado «NORMAS SUBSIDIARIAS» o «NORMAS SUBSIDIARIAS DE ALGUAZAS». Extrae los enlaces documentales de esa misma tarjeta, resuelve rutas relativas, exige documentos municipales HTTPS PDF/ZIP y agrupa todos sus enlaces sin duplicarlos en un único registro de identidad estable. No toma enlaces de tarjetas vecinas. La selección procede del inventario vivo, no de un registro precargado ni de la URL del ZIP fijada en el código.

El inventario inspeccionado está servido en una sola página, sin paginación observada. El parser falla si aparecen controles de paginación reconocidos: será necesario revisar el recorrido antes de aceptar una extracción parcial por páginas. También falla si desaparece la tarjeta o sus documentos, si cambia a enlaces inesperados o si la petición HTTP falla. No sustituye errores por una salida vacía satisfactoria.

Se excluyen tasas urbanísticas, formularios, ordenanzas fiscales y de limpieza de solares, planes de juventud/igualdad/subvenciones y noticias. La tarjeta «MODIFICACION BORM Nº 302 DE 31-12-2008 (está oculta)» no identifica suficientemente un instrumento urbanístico ni su relación con las NNSS, por lo que no se atribuye a ellas ni se crea un proyecto separado.

**Cobertura parcial: un instrumento documental municipal.** No es un inventario completo de planeamiento, modificaciones, expedientes ni obras públicas de Alguazas. Publicar el archivo en la web no prueba su vigencia jurídica. No se han extraído concesiones de licencias. No se inventan fechas, fase, coordenadas o geometría. Las fechas de la ruta de subida del ZIP no se interpretan como publicación, acuerdo o aprobación. Los campos de fechas se omiten al no disponer de una fecha semánticamente verificada. `publication_ready: false` y `geometry_status: unavailable` explicitan los límites. Licencias, programación y jitter quedan desactivados en el manifest.

## Validación reproducible y evidencia local

Pruebas: `python -m unittest municipio.test_alguazas -v` con el runtime indicado; **5 pruebas correctas**. Cubren agrupación de documentos, aislamiento frente a tarjetas ajenas, ausencia de fechas y geometría inferidas, errores ante inventarios vacíos/documentos ausentes/enlaces externos, detección de paginación, contrato de actualización completa, conservación de la salida anterior ante fallo de red y licencias desactivadas.

Ejecución real: instancia `AlguazasAyuntamientoAdapter('alguazas', config={'evidence_dir': 'evidence'})` y llamada a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro vivo**. Sin base de datos, publicación o geocodificación.

Evidencia local (no destinada a commit):

- `evidence/proyectos.jsonl`: registro extraído por el adaptador.
- `evidence/validation.json`: número de registros, URLs fuente, limitaciones, comprobación de firma de los nueve PDF, integridad y SHA-256 del ZIP.
- `evidence/inventory.html`: captura de la página obtenida en la ejecución del adaptador.
- `evidence/ordenanzas.html`, `evidence/agenda.html`: capturas de descubrimiento.
- `evidence/normas-subsidiarias.zip`, `evidence/archive-members.json`: archivo municipal real y listado de sus miembros. No se crean registros separados por plano ni se extraen archivos del ZIP al sistema de ficheros.
