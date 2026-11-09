# Guitiriz — Lugo — INE 27022

Investigación y extracción real: 9 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, `municipio/manifest.py` y los ejemplos de Chipiona
y Hernani. El adaptador cumple los cuatro métodos del contrato y se carga desde
el manifest, sin cambios en el registro compartido ni dependencias.

## Fuentes oficiales y alcance

Fuente utilizada: https://concellodeguitiriz.com/urbanismo/

Inventario municipal actual, servido completo en una página, sin paginación
observada. El enlace «Acceso ao Plan Xeral» identifica el PXOM municipal; la sección
«Plantexamento de desenvolvemento» contiene el «Estudo Detalle Avda. da Coruña e
rúa Fonte de San Blas». Resultado en vivo: **dos instrumentos**, uno por registro.
El parser descubre sus enlaces en el HTML, sin precargar expedientes. Agrupa los
anexos de cada tarjeta y elimina enlaces repetidos, sin mezclar instrumentos.
El PXOM se representa como un único instrumento con su paquete ZIP, no como un
registro por plano o capítulo. Se conserva la URL completa, incluido `?dl=0`.

Documentos publicados por el Concello:

- PXOM: https://www.dropbox.com/s/ute75iihkmfe23v/GUITIRIZ_PXOM_01.06.2020.zip?dl=0
- Estudio: [PDF municipal](https://concellodeguitiriz.com/wp-content/uploads/2022/07/Estudo-Detalle-Avda.-da-Corun%CC%83a-e-ru%CC%81a-Fonte-de-San-Blas..pdf).

La procedencia oficial del enlace del PXOM es la página municipal; Dropbox es
su alojamiento externo. No se verificó la descarga ni el contenido completo del
ZIP. El PDF del estudio sí se descargó: HTTP 200, `application/pdf`, firma `%PDF-`,
3.292.792 bytes. Sus primeras páginas confirman el título y la localización.

Durante el descubrimiento se revisó también
https://concellodeguitiriz.com/programas/ (captura local). No forma parte de esta
extracción: mezcla programas y convenios y requeriría otro parser para aislar
actuaciones materiales. No se presenta esta cobertura como inventario completo
de obras municipales. Se excluyen expresamente inventario de caminos, plan de
incendios, formularios de licencia, modelos de memoria, tasas, noticias y
contratación. No se ha identificado un registro verificable de licencias concedidas;
`licencias.enabled=false` y sus métodos no realizan peticiones.

Como contraste oficial del PXOM, el buscador localizó el
[BOP de Lugo de 16/10/2020](https://www.deputacionlugo.gal/sites/deputacionlugo.org/files/inline-files/16-10-2020.pdf),
que publica su normativa. No se integra como otro instrumento ni se usa para
precargar datos en el adaptador.

## Fechas, estado y limitaciones

Los registros son entradas de un inventario documental, sin atribuir vigencia
jurídica o ejecución material. No incluyen fechas: la página índice no ofrece
fechas inequívocas de publicación o acuerdo para cada entrada. El nombre del
ZIP y los directorios de subida no se convierten en fechas de aprobación.
El PDF del estudio contiene una diligencia que menciona aprobación definitiva
en pleno de **30/09/2021** y firma de **19/01/2022**: son eventos diferentes,
y ninguno equivale a la fecha de publicación web. Estas fechas se documentan
aquí como comprobación manual; el parser de HTML no las extrae ni las afirma
en sus registros. Tampoco se deducen fechas de los metadatos del CMS.

Sin coordenadas ni geocodificación sintética: `geometry_status=unavailable`,
`publication_ready=false`, `geocode.jitter_missing=false` y `schedule.enabled=false`.
Cobertura parcial: PXOM y planeamiento de desarrollo enlazados actualmente,
sin archivo histórico, seguimiento de cambios legales o inventario total de
obras públicas. Una actualización refresca la instantánea, sin simular un cursor
incremental. Si aparecen controles de paginación, desaparece la estructura
esperada o surge una tarjeta de desarrollo no reconocida, el adaptador falla
explícitamente antes de reemplazar la salida.

## Verificación reproducible y evidencias locales

Runtime empleado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_guitiriz -v
```

Ocho pruebas correctas: agrupación y aislamiento de documentos, exclusiones,
identidad estable y Unicode, ausencia de fechas/coordenadas inventadas,
rechazo de cambios de estructura y paginación, refresco conservando salida ante
fallos y licencias desactivadas. También se comprueba la carga del manifest.

Se ejecutó realmente `GuitirizAyuntamientoAdapter.backfill_proyectos` contra el
portal con la configuración local `evidence_dir=evidence`:

- `evidence/proyectos.jsonl`: dos registros reales.
- `evidence/validation.json`: `live_records`, URLs, limitaciones, comprobación PDF y pruebas.
- `evidence/urbanismo.html` y `evidence/programas.html`: capturas de fuentes.
- `evidence/estudo-detalhe.pdf` y `evidence/estudo-detalhe-first-pages.txt`: documento y verificación textual.

Las evidencias son locales, no forman parte de los cuatro archivos fuente.
No se accedió a bases de datos ni se publicó contenido.
