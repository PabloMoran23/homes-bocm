# Porto do Son — INE 15071, A Coruña

Investigación y extracción real: 8 de noviembre de 2026. Se revisaron previamente
`municipio/adapters/portal.py`, `municipio/manifest.py`, el registro de adaptadores
y los ejemplos y manifests de Manlleu, Chipiona y Hernani.

## Fuentes oficiales y alcance

Inventario utilizado: https://portodoson.gal/category/obras/proxectos/

La sección municipal https://portodoson.gal/servizos/obras/ distingue sus proyectos
de sus noticias de obras y enlaza las mismas actuaciones. El archivo Proxectos
ofrece las cinco fichas completas en una sola página, sin enlaces de paginación
en la respuesta observada. El adaptador recorre los enlaces de paginación si
aparecen, deduplica fichas y falla si páginas distintas repiten el mismo listado.
No aplica un límite silencioso de páginas. Una respuesta vacía, un error HTTP o
un documento desaparecido de una ficha admitida impiden escribir un nuevo
snapshot. Cada actualización vuelve a consultar el inventario completo.

Resultado: **cuatro registros reales y cinco documentos PDF**:

- [PEID educativo de Portosín](https://portodoson.gal/aprobacion-definitiva-peid-construcion-de-equipamento-educativo-en-portosin/): un instrumento, con dos documentos agrupados, el plan y el certificado del Pleno. La narración municipal identifica expresamente la aprobación definitiva el 14 de enero de 2025. La fecha del artículo es el 16 de enero de 2025.
- [Humanización de Cruceiro](https://portodoson.gal/humanizacion-do-nucleo-do-cruceiro/): ficha con localización parroquial, presupuesto y plano PDF.
- [Humanización de Basoñas, segunda fase](https://portodoson.gal/umanizacion-do-nucleo-de-basonas-2a-fase/): ficha con localización parroquial, presupuesto y plano PDF. Se conserva la URL real, que comienza con `umanizacion`.
- [Humanización de A Silva](https://portodoson.gal/humanizacion-do-nucleo-da-silva/): ficha con presupuesto y plano PDF.

Las tres humanizaciones se publicaron el 11 de marzo de 2024. No se infieren
fechas de acuerdo, aprobación, comienzo o finalización de esas fechas de CMS.
Los presupuestos se conservan en la descripción original, sin reinterpretarlos.
Las imágenes de portada no se convierten en geometrías.

La quinta ficha, [adquisición de un inmueble en Outeiro Alto](https://portodoson.gal/adquisicion-do-inmoble-situado-na-rua-outeiro-alto/),
solo describe una adquisición con presupuesto e imágenes. Se excluye al no
acreditar en esa ficha una intervención física; figura en el informe de exclusiones.
El filtro acepta exclusivamente PEID con aprobación explícita y obras de
humanización nombradas con narrativa y PDF. No convierte cualquier entrada de
la categoría en un proyecto. Nuevas tipologías quedan registradas como excluidas.

## Otras fuentes descubiertas y límites

La [oficina de urbanismo](https://portodoson.gal/servizos/urbanismo/) informa sobre
servicios y solicitudes de licencias, no acredita un registro de concesiones.
Una primera petición devolvió HTTP 403; no se emplea como fuente del adaptador.
[Documentación municipal](https://portodoson.gal/documentacion/) contiene formularios,
que no se incorporan como licencias ni proyectos.

También se comprobó la antigua [ficha del PXOM](https://portodoson.gal/plan-xeral-de-ordenacion-municipal/),
que enlaza un PDF, y el [inventario autonómico SIOTUGA](https://siotuga.xunta.gal/siotuga/urb),
que identifica Porto do Son con código 15071. No se mezclan esos inventarios con
Proxectos: no se afirma cubrir todo el planeamiento municipal ni todo el archivo
Obras, anuncios de contratación, nuevas noticias de actuaciones o expedientes
históricos. La antigüedad de las cuatro fichas no implica que esas obras sigan
en ejecución actualmente. Se extraen los proyectos documentados que el
inventario oficial mantiene publicados.

Cada registro conserva su ficha, el inventario, la descripción original y los
PDF agrupados con su página de procedencia. La fecha explícita de aprobación
incluye también su URL de procedencia. No se añaden coordenadas, fechas de
acuerdo desconocidas o concesiones de licencia. `publication_ready: false` y
`geometry_status: unavailable` expresan la ausencia de geometría verificada.
El manifest desactiva licencias, programación y jitter de coordenadas.

## Verificación y evidencia local

Runtime empleado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_porto_do_son -v`: **6 correctas**. Cubren
agrupación y aislamiento de documentos, publicación frente a aprobación,
exclusión de formularios/licitaciones/noticias/adquisiciones, fallo ante cambios
de estructura, recorrido de varias páginas, detección de repetición de páginas,
conservación del snapshot anterior ante fallo y restricciones del manifest.

Se ejecutó `PortoDoSonAyuntamientoAdapter.backfill_proyectos` con peticiones HTTP
reales, sin bases de datos ni publicación. `evidence/proyectos.jsonl` contiene
los cuatro registros y `evidence/validation.json` registra recuento, URLs,
limitaciones, exclusiones y comprobaciones documentales. Se guardaron las seis
respuestas HTML utilizadas en `evidence/captures/`. Los cinco PDF respondieron
HTTP 200 con firma `%PDF-`; solo se descargaron y guardaron sus primeros 4096
bytes, sin afirmar haber interpretado su contenido completo. Capturas de otras
páginas consultadas permanecen bajo `evidence/`. Toda evidencia es local y no
forma parte de los cuatro archivos fuente.
