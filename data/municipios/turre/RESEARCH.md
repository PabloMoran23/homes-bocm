# Turre — INE 04093, Almería

Investigación y extracción en vivo: 9 de noviembre de 2026. Implementación de un
único adaptador municipal, sin cambios compartidos ni dependencias nuevas.

## Fuentes oficiales descubiertas

- [Web del Ayuntamiento](https://www.turre.es/): el pie identifica Turre,
  Almería y CIF P-0409300-A. La sección Ayuntamiento enlaza normas,
  transparencia y sede electrónica.
- [Normas municipales](https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_categoria1.xsp?cat=Normas&p=Turre):
  incluye la categoría Planeamiento Urbanístico.
- [Inventario temático usado por el adaptador](https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_rol_categoria2.xsp?cat2=Planeamiento+Urban%C3%ADstico&p=Turre).
- [Tablón de la sede, por temas](https://www.dipalme.org/Servicios/cmsdipro/index.nsf/tablon_view_categoria123.xsp?p=SedeTurre):
  muestra también contratación, subvenciones y otros asuntos; esas categorías
  no forman parte de esta extracción.
- [Catálogo municipal de datos abiertos](https://www.turre.es/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=957CC3AB9F60F48FC1258908002F194D&p=Turre):
  enumera competencias; no constituye un inventario de proyectos o licencias.

No se usa una lista de expedientes precargados. Cada ejecución lee el inventario
actual y descubre las fichas. El HTML inicial tiene tres categorías plegadas:
Normas, Normas en Trámite de Aprobación y Territorio. Se despliegan mediante
los controles públicos XPages, con su estado anónimo y una sesión HTTP, hasta
que no queden controles `expand.gif`. Son peticiones de navegación del tablón,
no solicitudes administrativas. Se verifican errores HTTP, origen, estructura,
avance y ausencia de paginación. El inventario observado, totalmente desplegado,
contiene nueve anuncios y un pie sin controles de paginación. Si aparecen
paginadores nuevos, se lanza un error explícito en lugar de devolver datos
truncados. No se consulta el tablón histórico.

## Resultado y agrupación

Seis fichas seleccionadas producen **cuatro registros** y **doce enlaces
documentales únicos**, con título, URL y ficha de procedencia de cada documento:

| Instrumento/proyecto | Publicaciones de las fichas | Documentos |
| --- | --- | --- |
| Innovación n.º 11 del PGOU, SUE R-2, expediente 2018/409367/003-502/00001 | 18/05/2022 | 4: anexos I/II, certificado, memoria/resumen ejecutivo, planos |
| Reparcelación Unidad G, Polígono 1, R-4 Cortijo Grande, expediente 2020/409367/003-626/00001 | 11/07/2022 y rectificación 15/12/2022 | 4: anuncio original, rectificación, certificado, proyecto/anexo disociado |
| Proyecto de actuación del refugio público en Los Moralicos, Sierra Cabrera | 23/11/2021 | 2: anuncio y publicación BOP |
| Modificación del Plan Parcial Sector R-2, inscripción y corrección de errores | 05/03/2019 y 07/08/2019 | 2: inscripción y texto corregido |

Fichas fuente completas:

- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=9DF4956FED90DE84C12588460039021C
- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=D9A42017A7692D1DC125887C00261FEE
- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=007778503F0BD4BCC125891900290D53
- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=F7C5DAAD8EA1D0D7C1258796002B7645
- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=DD74FA168760928FC12583B400279658
- https://www.turre.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Turre&documentId=90513C74461DBAC2C125844F00248B30

La reparcelación se agrupa por el expediente literal compartido. Para las dos
fichas del Plan Parcial R-2 sin expediente en el título, se verificaron los PDFs
enlazados: BOP 43 de 05/03/2019, página 14, y BOP 150 de 07/08/2019, página 15.
Ambos identifican la misma modificación, aprobada el 11/06/2009, con inscripción
autonómica 7918. Esa relación documental está explicitada como mapa de identidad
entre ambas fichas en el código. No se agrupan instrumentos distintos solo por
compartir sector: la innovación n.º 11 se mantiene separada. Otros expedientes
o fichas conservan identidad propia. Los documentos de las publicaciones
agrupadas se retienen todos, sin crear un proyecto por cada PDF.

Se excluyen los tres anuncios del sector I.1 sobre bases/estatutos, ampliación
del acuerdo y escritura de la junta de compensación: no documentan por sí mismos
un proyecto físico ni un instrumento de planeamiento. La validación enumera sus
títulos y URLs. Se rechazan formularios, licencias, licitaciones y contratación.

## Semántica y límites

`fecha_publicacion` es exclusivamente el valor «Publicado» de la ficha principal;
`publicaciones` conserva por separado las fechas de todas las fichas asociadas.
La ficha principal es la primera publicación que no sea corrección/rectificación.
No se toman fechas de nombres de archivo, fechas de firma ni referencias BOP como
fechas de aprobación. El parser no extrae texto PDF, por lo que `fecha_acuerdo`
y `fecha_aprob` son nulas incluso donde la revisión documental permite conocer
una fecha histórica. Los títulos se conservan literalmente; no se infiere fase,
vigencia jurídica ni ejecución de obras.

Cobertura parcial: inventario temático actual, no historial completo de
planeamiento, proyectos, BOP ni obras municipales. Los PDFs se enlazan sin
descargarlos todos en cada ejecución. Se descargaron dos PDFs R-2 para verificar
la agrupación (respuesta HTTP correcta, firma PDF, conversión local con
`pdftotext`); las capturas y sus textos permanecen en evidencia local.

No se verificó un registro de licencias concedidas: `licencias.enabled=false`.
Sin geometrías verificadas: `lat`, `lon` y `geometry` nulos,
`geometry_status=unavailable`, `publication_ready=false`. Se desactivan
`schedule.enabled` y `geocode.jitter_missing`.

## Validación reproducible

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_turre -v`, **12 correctas**.
Cubren agrupación y aislamiento, procedencia de anexos, fechas, exclusiones,
cambios de estructura, paginación inesperada, navegación XPages, falta de avance,
identidad del manifiesto y conservación de la salida anterior ante fallos.

Ejecución real realizada mediante `load_manifest('turre')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `adapter.config['capture_dir']='evidence'`. La política de entidades compartida
se aplica por el cargador sin modificar código común; informa cuatro registros y
estado `ok` (una categoría desconocida, sin alterar las identidades extraídas).

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: cuatro registros reales.
- `evidence/validation.json`: `live_records=4`, URLs, exclusiones, límites,
  runtime, fecha UTC y resultado de pruebas/política de entidades.
- `evidence/inventory-00.html` a `inventory-03.html`: navegación real completa.
- `evidence/notice-*.html`: fichas oficiales capturadas.
- `evidence/DD74FA168760928FC12583B400279658.pdf` y
  `evidence/90513C74461DBAC2C125844F00248B30.pdf`, con sus textos locales.

No se publicaron datos ni se utilizaron bases de datos, credenciales o despliegues.
