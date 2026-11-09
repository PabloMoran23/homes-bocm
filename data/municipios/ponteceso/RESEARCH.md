# Ponteceso — INE 15068, A Coruña, Galicia

Verificación y extracción en vivo: 2026-11-09. Adaptador único de planeamiento;
licencias y programación deshabilitadas, sin desplazamiento aleatorio de puntos.

## Descubrimiento y autoridad

La portada oficial https://www.ponteceso.gal/ga/web/ ofrece un banner PXOM
(`a[href="click.php?cod=23"]`, imagen del plan). Su redirección
https://www.ponteceso.gal/ga/web/click.php?cod=23 conduce al inventario municipal
http://www.ponteceso.net/PXOM/pxom.html, disponible también por HTTPS:
https://www.ponteceso.net/PXOM/pxom.html. Se conserva la evidencia del enlace y
su destino. El dominio histórico no se presupone oficial por su nombre.

El inventario documental responde HTTP 200 y agrupa normativa, ordenación,
catálogo y participación pública del PXOM, además de MR-Lestimoño. Se leen TODOS
los enlaces PDF de `a` y `area` (mapas de imagen), sin convertir hojas de planos
en proyectos separados. Enlaces repetidos se deduplican por URL, normalizando
espacios. Cada documento conserva título, URL y página de procedencia.

La página de Urbanismo https://ponteceso.gal/ga/web/index.php?dep=1&idc=35&mod=des
contiene una ordenanza y anexos, no un registro de concesiones. Los trámites de
https://sede.ponteceso.gal/sxc/es/procedimientosytramites/ son solicitudes,
no licencias otorgadas. No se extraen como proyectos ni licencias. Noticias y
perfil del contratante tampoco son fuentes de registros de este adaptador.

## Registros y fechas

Extracción real mediante el manifest y `load_portal_adapter`:

- **PXOM de Ponteceso**: 112 enlaces documentales, incluidos 111 del inventario
  y el DOG de aprobación. La orden autonómica está fechada el **2015-05-06**;
  el DOG la publica el **2015-05-22**. La fuente le impone condiciones.
- **Modificación MR-Lestimoño**: 14 documentos (DOG, memoria, cuatro planos de
  información y ocho de ordenación), un solo instrumento relacionado con el PXOM.
  `fecha_publicacion=2019-03-29` procede del rótulo explícito «DOG 29/03/19».
  No se asignan fase ni fecha de aprobación automáticamente a partir de ese rótulo.

El DOG del PXOM, descubierto en el inventario, se consulta en su dominio actual:
https://www.xunta.gal/dog/Publicados/2015/20150522/AnuncioCA02-190515-0005_gl.html.
El parser extrae las fechas de orden y publicación del título, comprobando que se
refiere al PXOM de Ponteceso. El inventario municipal llama definitiva a la sesión
plenaria del 9 de marzo de 2015, pero el DOG la describe como **provisional**;
por eso NO se usa esa fecha como aprobación definitiva. `fecha` y
`fecha_acuerdo` quedan nulas, sin confundir publicación y acuerdo.

El PDF municipal del DOG de MR-Lestimoño está disponible y se ha capturado:
https://www.ponteceso.net/PXOM/PXOM/DOG290319NORMATIVA.PDF.
Su lectura confirma una orden de 13 de marzo de 2019 publicada el 29 de marzo.
Esta comprobación documental se conserva como evidencia, pero el adaptador no
parsea PDFs y deja `fecha_aprob` nula para la modificación. No se codifica esa
fecha como constante sin extraerla de la fuente en cada ejecución.

## Cobertura y límites

Es una instantánea completa de los dos grupos documentales en esta página,
**no** un inventario exhaustivo de planeamiento u obras del municipio. El pie de
página dice actualizado en julio de 2015 aunque contiene documentos de 2019;
no se utiliza como fecha de actualización ni publicación de los instrumentos.
El enlace al plan de 2002 se excluye porque la propia página lo declara sustituido.
Se conserva el enlace a la consulta de la Xunta en la captura, sin afirmar que
se haya recorrido ese registro. La búsqueda oficial revela modificaciones
posteriores, por ejemplo MP/PXOM número 2 en el registro autonómico:
https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador?page=15.
No forman parte de esta cobertura municipal; no se afirma vigencia consolidada.

No hay paginación en el inventario inspeccionado. Si aparecen controles de
paginación, un PDF sin clasificación conocida, desaparece un grupo o cambia
el contenido identificativo del DOG, la ejecución falla antes de reemplazar el
resultado. No se corta una lista por número de registros ni por fecha. Los updates
refrescan la página entera; no mantienen un archivo histórico de instrumentos
retirados. Se conservan todos los enlaces, pero no se ha comprobado la descarga
de cada PDF. La captura representativa del DOG de 2019 sí fue comprobada como PDF.

## Geometría

`geometry_status: unavailable`. Los documentos cartográficos son PDFs, no una
geometría vectorial verificada por expediente. El enlace de Google Maps es la casa
consistorial, no el ámbito del plan. El inventario también enlaza una consulta de
SIOTUGA, pero no se ha verificado una capa vectorial asociada a estos registros.
No se georreferencian PDFs ni se inventan coordenadas o CRS. `lat`, `lon` y
`geometry` son nulos; `publication_ready=false`.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_ponteceso -v`: **6 pruebas pasan**. Comprueban
agrupación y deduplicación de mapas, fechas y su procedencia, rechazo de páginas
incompletas/paginadas/documentos nuevos, preservación de salida si falla el DOG,
licencias sin red y carga del manifest por el registro compartido.

Ejecución real: `load_manifest('ponteceso')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con configuración local
`evidence_dir='evidence'`. Resultado: **2 registros, 126 enlaces documentales**.
El anotador compartido de categorías informa dos categorías desconocidas; se
conserva ese resultado sin alterar la política compartida.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/pxom-inventory.html`, `evidence/pxom-dog.html`,
`evidence/mr-lestimono-dog.pdf`, texto del PDF y capturas de descubrimiento.
No se publica ni sincroniza ningún dato. La evidencia queda fuera de los cuatro
archivos fuente y fuera de cualquier commit.
