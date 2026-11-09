# Porqueres — INE 17137, Girona

Investigación y extracción real: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

- [Documents i projectes en fase d’exposició pública](https://porqueres.cat/tramits-exposicio-publica/): inventario municipal seleccionado. Publica títulos, expedientes, estados de aprobación, enlaces al tablón y códigos seguros de verificación de los documentos. Se observaron 21 entradas: 19 actuaciones admitidas y dos exclusiones (plan de igualdad y exposición de licencia ambiental de la deixalleria).
- [Planejament i gestió en tràmit](https://porqueres.cat/planejament-en-tramit/planejament-en-tramit/): inventario separado de modificaciones del POUM, proyectos de urbanización, reparcelación y otros instrumentos. Descargado para investigación, fuera de la cobertura del adaptador.
- [Planejament i gestió vigent](https://porqueres.cat/planejament-en-tramit/planejament/): inventario separado de planeamiento vigente y convenios. Descargado para investigación, fuera de la cobertura del adaptador.

Las tres páginas se consultaron directamente mediante HTTP y se conservaron en `evidence/`. No se usa un buscador como fuente de registros ni se extraen noticias o anuncios de contratación.

## Cobertura y agrupación

El adaptador extrae el inventario actual de obras y su plan director de abastecimiento de agua: **19 registros y 23 referencias documentales** en la ejecución en vivo. Incluye franjas de prevención de incendios, acera/carril bici, mejora hidráulica, paisaje de Santa Maria, climatización de biblioteca, instalación fotovoltaica de guardería, redes de saneamiento, alumbrado, pista polideportiva, carpinterías escolares, restauración de humedales, agua del pabellón, caminos, falso techo del centro cívico, piscina, asfaltado e instalaciones deportivas.

Un registro representa un expediente publicado. La identidad deriva del número de expediente; no de su posición ni de una URL genérica compartida. Proyecto, planos y versiones de precios se agrupan conservando cada CSV y su etiqueta de origen. Las repeticiones compatibles se agrupan; las contradictorias provocan error.

Los enlaces de documento son los validadores que publica el ayuntamiento, con el CSV como campo separado: **no son enlaces directos de descarga**. Se requiere introducir el CSV en el validador municipal. No se descargó ni interpretó el contenido de los proyectos. La evidencia acredita la publicación de cada referencia en el inventario. Los enlaces de anuncio se conservan aparte; muchos son portadas genéricas del tablón. Biblioteca y fotovoltaica comparten el mismo enlace de edicto en la fuente; se conserva tal cual, sin fusionar esos expedientes distintos.

El inventario observado está completo en una página estática. No se aplican límites de número de registros. El parser rechaza controles de paginación reconocidos y enlaces de continuación para evitar truncar una futura versión paginada. También falla ante contenedor/título ausente, inventario vacío, falta de códigos/validador o pérdida de delimitación entre expedientes. La actualización refresca la instantánea completa; no construye un archivo histórico ni prueba que las entradas retiradas hayan dejado de estar vigentes.

## Semántica y límites

La fase inicial o definitiva procede únicamente del texto de cada sección del inventario. Es una afirmación publicada por el ayuntamiento, sin comprobación independiente del acuerdo, vigencia o ejecución física. La memoria del falso techo dice «Aprovació de la memòria» sin distinguir inicial/definitiva: `fase` queda nula y se conserva el texto original.

`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas: el inventario no proporciona fechas de evento por expediente. Los años del expediente y los meses de las versiones documentales no son fechas de aprobación. No se confunde la publicación del CMS con un acuerdo.

Sin geometría ni coordenadas verificadas: `lat`, `lon`, `geometry` nulos, `geometry_status: unavailable`, `publication_ready: false`. Manifest con `schedule.enabled: false`, `geocode.jitter_missing: false` y `licencias.enabled: false`. La exposición de una licencia ambiental no acredita una concesión y se excluye. No se verificó un registro público de licencias concedidas.

Cobertura parcial explícita: únicamente el inventario seleccionado, sin archivo histórico, inventarios separados de planeamiento ni exhaustividad de todas las obras municipales.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_porqueres -v`: seis pruebas correctas, incluyendo agrupación de documentos y versiones, aislamiento entre expedientes, exclusión de licencias/formularios/licitaciones y documentos ajenos a obra, fechas desconocidas, rechazo de paginación y conservación del resultado anterior si falla la actualización.

Extracción real: carga del manifest, importación de `portal.adapter`, llamada a `backfill_proyectos` con `capture_dir=evidence` y salida `evidence/proyectos.jsonl`. No se accede a bases de datos ni se publica nada. Resultado: 19 identidades únicas, 23 documentos con procedencia. `evidence/works-live.html` contiene la respuesta exacta procesada; `evidence/validation.json` registra recuentos, fuentes, hash de captura y limitaciones. Las capturas de las otras dos fuentes son únicamente evidencia de investigación. Toda la evidencia es local y no forma parte de los cuatro archivos fuente.
