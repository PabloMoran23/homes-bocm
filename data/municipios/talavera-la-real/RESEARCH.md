# Talavera la Real — INE 06128, Badajoz

Investigación y extracción en vivo: 9 de noviembre de 2026. Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro dinámico de adaptadores y los ejemplos Manlleu y Chipiona. Sin cambios compartidos ni dependencias nuevas.

## Fuente oficial y descubrimiento

El [portal SITEX de la Junta de Extremadura](https://sitex.juntaex.es/SITEX/planeamiento) contiene el inventario de planeamiento municipal. Su selector público identifica expresamente `176` como Talavera la Real; es un identificador interno SITEX, distinto del INE 06128. El observador JavaScript del selector consulta mediante POST `https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat` con el campo `municipioseleccionado=176`. Un GET de ese endpoint no aplica el filtro: el adaptador replica la consulta POST pública, sin iniciar sesión ni enviar formularios de incidencias.

El árbol completo observado contiene **76 figuras**, todas recorridas, incluidas ramas históricas y expedientes en trámite: 42 «Vigente», 19 «En trámite», 14 «No vigente» y 1 «En Trámite Pte Homologación». No se observó paginación, carga diferida de ramas ni límite de resultados en ese árbol; cada enlace `addTab` conduce a una ficha individual. El adaptador rechaza inventarios vacíos, identidad municipal incorrecta, referencias contradictorias o aparición de controles de paginación. No hay un límite que corte el árbol. Ante un error de ficha no escribe una instantánea parcial.

Ejemplos extraídos del inventario, no precargados en el código:

- [Revisión NNSS.R-001](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/33542): aprobación definitiva 24/08/1993 y publicación 09/12/1993, según campos explícitos de SITEX.
- [Modificación 1/2025, calle Bolivia](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40923), referencia NNSS.R-001.M-058: aprobación inicial de 28/05/2025, anuncio DOE de 19/06/2025 y trámites de 2026. No tiene Fecha AD en la ficha: no se fabrica una aprobación definitiva a partir del depósito o de la aprobación provisional.
- [Modificación 2/2025, Aldea del Conde](https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40924), NNSS.R-001.M-059.

Se investigó también `https://talaveralareal.es/` y su variante `www`: ambos fallaron la verificación TLS por discrepancia del nombre del certificado. No se desactivó TLS. Las búsquedas oficiales en DOE corroboran publicaciones municipales recientes, como [información pública de 2/2025](https://doe.juntaex.es/otrosFormatos/html.php?anio=2025&doe=1170o&xml=2025081004); no se usa una selección de resultados de buscador como inventario. El alcance elegido es el árbol oficial SITEX, que puede estar incompleto o desactualizado respecto a otros canales municipales.

## Unidad y semántica

Un registro por identificador oficial de figura SITEX, con referencia jerárquica y título real del inventario. Las modificaciones son instrumentos propios; memorias, planos y boletines de una figura se agrupan en `documentos`, sin generar un proyecto por PDF. Se conservaron **264 enlaces documentales dentro de 73 fichas** (conteo por instrumento, sin afirmar unicidad global). Cada documento conserva su ficha de procedencia. Los paneles de documentos están incluidos en el HTML, aunque visualmente estén plegados. Los formularios y enlaces generales del menú no entran en los registros.

`fecha_aprob` corresponde exclusivamente a «Fecha AD»; `fecha_publicacion` a «Fecha de publicación AD». Fechas y enlaces de información pública, informes, aprobaciones iniciales/provisionales y otros trámites permanecen en `tramites`. Se conserva por separado el depósito. `fecha_acuerdo` y la fecha genérica son nulas: no se deducen de publicaciones. `estado_fuente` reproduce SITEX sin convertirlo en una fase jurídica inferida. Los estados históricos no se presentan como planeamiento vigente certificado. Los enlaces documentales se conservan sin afirmar que cada descarga haya sido comprobada o que su texto haya sido interpretado.

La procedencia real en cada registro es `junta_extremadura` / SITEX; `proyectos.source: ayuntamiento` es el canal municipal del esquema existente. La cobertura es de instrumentos de planeamiento, no de todas las obras municipales, ni de licencias otorgadas. No se incorporan anuncios de contratación ni noticias genéricas. Licencias y ejecución programada desactivadas. Sin coordenadas, geometrías o jitter inventados; `publication_ready: false` en todos los registros.

## Verificación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_talavera_la_real -v` — **7 correctas**. Comprueban identidad municipal y de figura, fechas diferenciadas y ausentes, agrupación/aislamiento de documentos, exclusión de formularios, rechazo de paginación/vacíos, escritura completa, refresco y licencias desactivadas.

Ejecución real mediante `load_manifest` y `load_portal_adapter`, llamando solo a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence/captures`. La evidencia local incluye `proyectos.jsonl`, `validation.json` (recuento, URLs consultadas y limitaciones), `tests.txt`, capturas del inventario y de las 76 fichas. No hay publicación, base de datos, geocodificación ni ejecución de pasos globales.

Comprobación documental adicional: [Memoria justificativa b128j.pdf](https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/865), vinculada a NNSS.R-001: HTTP 200, Content-Type `application/octet-stream`, firma `%PDF-` válida. Solo se capturaron los primeros 8192 bytes, no el documento completo; detalle en `evidence/document-check.json`.

La evidencia está excluida del control de versiones por la configuración existente y no forma parte de los cuatro archivos fuente.

La anotación compartida reconoce 73 referencias como expedientes. Las tres referencias raíz sin número (`PGM`, `PDSU`, `NNSS`) quedan pendientes de clasificación automática pese a tener ficha e identidad verificadas; se conservan con sus estados y documentos. No se inventa un número de expediente para modificar ese resultado. El informe de anotación final no presenta incidente por pico de entidades desconocidas.
