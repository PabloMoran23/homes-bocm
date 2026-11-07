# Tarazona — Zaragoza — INE 50251

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

La página del servicio municipal de Urbanismo enlaza al árbol del PGOU:
https://www.tarazona.es/tu-ayuntamiento/servicios-y-areas-municipales/urbanismo

Inventario seleccionado:
https://www.tarazona.es/tarazona-tematico/urbanismo-y-obras-publicas/plan-general-ordenacion-urbana

Se recorren sus dos secciones, `documentacion-escrita` y
`documentacion-grafica`, y las seis subsecciones gráficas enlazadas:
`documentacion-grafica-0` (clasificación), `-7` (gestión), `-5` (estructura y
ordenación), `-1` (zonificación), `-3` (alineaciones) y `-4` (ordenanzas y
catálogo). Todas estas rutas dependen de la URL del inventario anterior.
La sección escrita repite el texto refundido de la portada. La sección gráfica
incluye la lista de planos. Los documentos se extraen del cuerpo del nodo Drupal,
no del menú general ni de noticias. El árbol observado tiene nueve páginas sin
paginación; el adaptador sigue también enlaces de paginación dentro del árbol,
deduplica las visitas y falla si hay un paginador externo o una página inaccesible.
No hay un límite que devuelva silenciosamente una fracción del recorrido.

Se consultó también el portal temático:
https://www.tarazona.es/tarazona-tematico/urbanismo-y-obras-publicas
Contiene noticias, avisos y enlaces de servicios; sus tarjetas recientes no se
utilizan como inventario completo de proyectos. No se ha verificado un registro
público de licencias concedidas. Formularios y anuncios de contratación no se
convierten en licencias ni proyectos.

## Cobertura, agrupación y semántica

Resultado vivo: **1 instrumento real, el PGOU de Tarazona**, con **35 URL
documentales únicas**, procedentes de nueve páginas. El identificador deriva de
la URL estable del instrumento. El texto refundido, lista de planos y planos son
documentos del mismo instrumento, no 35 actuaciones independientes. Cada enlace
conserva título, sección y páginas de procedencia; `apariciones` retiene las
etiquetas originales incluso cuando comparten URL. En la sección de ordenanzas,
«F-20 Ordenanzas Especiales» y «F-20 B Conjunto Histórico alturas» apuntan al mismo
archivo municipal. Se conserva esa discrepancia sin inventar una URL alternativa.

Es una instantánea del inventario actualmente publicado, con **cobertura parcial**
del municipio. No acredita que todos los documentos sean de la misma versión ni
que todo el PGOU esté vigente. El directorio `Pgou_2022`, la fecha del CMS
«Última actualización: 01/07/2026» y el calendario lateral no acreditan fechas de
publicación, acuerdo o aprobación del instrumento. Estos campos quedan nulos;
no se infieren fase ni ejecución. No se generan coordenadas ni geometría a partir
de los planos. `publication_ready=false` y `geometry_status=unavailable`.

## Verificación y evidencia local

`python -m unittest municipio.test_tarazona -v`: cinco pruebas correctas sobre
agrupación, duplicados con distinta etiqueta, procedencia, recorrido paginado
con ciclos, exclusión de formularios/enlaces ajenos, fallo por cambio de estructura,
paginador externo, fallo de una página posterior y opciones del manifest.

Se cargó el manifest mediante `load_manifest` y el adaptador mediante
`load_portal_adapter`, y se ejecutó realmente `backfill_proyectos`. La política
compartida de entidades lo anota con categoría desconocida (1/1); no se fuerza
una categoría ni se modifica código compartido.

Evidencia local, sin incorporar al código fuente:

- `evidence/proyectos.jsonl`: registro real con enlaces y procedencia.
- `evidence/validation.json`: recuentos, URL visitadas, limitaciones y muestra documental.
- `evidence/*.html`: capturas de las páginas consultadas, incluidas capturas de
  cada respuesta de la ejecución del adaptador identificadas por hash de URL.
- `evidence/texto-refundido-prefix.bin`: primeros 2048 bytes del texto refundido,
  HTTP 200, `application/pdf`, firma `%PDF-` correcta, sin redirección.

Muestra comprobada:
https://www.tarazona.es/sites/default/files/documentos/Urbanismo/Pgou_2022/texto_refundido_del_plan_general_de_ordenacion_urbana_de_tarazona.pdf

La comprobación de la muestra no equivale a descargar ni validar íntegramente
los 35 documentos. La actualización repite el recorrido completo del inventario;
no usa una fecha CMS como cursor. Licencias, programación automática y jitter
geográfico están desactivados. No se ha publicado ni sincronizado ningún dato.
