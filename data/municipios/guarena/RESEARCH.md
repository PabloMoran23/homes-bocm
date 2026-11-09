# Guareña — INE 06060, Badajoz, Extremadura

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

El [portal institucional del Ayuntamiento](https://aytoguarena.es/) enlaza, en
Temas, el [Plan General Municipal](https://aytoguarena.es/temas/plan-general-municipal/).
Este último es el inventario que consume el adaptador: página Elementor
`data-elementor-type="wp-page"`, encabezado `Plan General Municipal`, botones
con enlaces PDF bajo `/recursos/pdf/plan-general-municipal/`. No se usa la
navegación, los posts incrustados, las noticias ni los modelos de solicitud como
registros. Se revisaron primero `municipio/manifest.py`, el contrato de
`municipio/adapters/portal.py`, los manifests existentes y los adaptadores de
Chipiona y Manlleu. No fue necesario modificar el registro compartido: el manifest
identifica la clase importable.

El inventario actual contiene **13 documentos, agrupados en un único instrumento**:
catálogo estructural, memoria detallada, memoria estructural, normativa detallada,
normativa estructural, evaluación ambiental, catálogo de bienes inventariados,
memoria y planos de información, ordenanzas gráficas de Guareña y Torrefresneda,
catálogo territorial, catálogo urbano y planos de ordenación estructural.
El registro conserva todos los títulos, URLs y la página de procedencia en
`documentos`. Torrefresneda aparece en los documentos del término municipal de
Guareña; no se genera otro municipio ni otro instrumento por ese plano.

Como contraste oficial adicional se descubrió la ficha de Diputación
[Planeamiento urbanístico general](https://www.dip-badajoz.es/impulsaodsmunicipal/actuaciones/13124/430),
que describe la redacción de un nuevo plan. No se ingiere: duplicaría el PGM y
sus objetivos de aprobación no prueban que se haya aprobado. La memoria
estructural del propio Ayuntamiento define el ámbito como el término de Guareña
(Badajoz), compuesto por Guareña y Torrefresneda, y explica la elaboración conjunta
de los componentes estructural y detallado.

## Semántica y limitaciones

Cobertura parcial: inventario documental actualmente publicado, sin histórico
completo de instrumentos, modificaciones, proyectos u obras. Los 13 documentos
no son 13 proyectos independientes. No se acredita vigencia, concesión de licencia
ni fase administrativa. La página no expone fechas administrativas verificables:
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas. Ni el año y
mes del rótulo, ni `20230608` en el nombre del fichero, ni las fechas del CMS o la
cabecera dinámica se convierten en fechas de aprobación/publicación.

No se extraen geometrías de los planos ni se asigna el centro municipal al
instrumento. Coordenadas y geometría nulas; `publication_ready=false`.
`licencias.enabled=false`: los formularios de obra mayor/comunicación de obras
del portal no son concesiones. `schedule.enabled=false` y
`geocode.jitter_missing=false`.

El inventario observado está íntegro en una sola página, sin paginación. Se
recorren todos sus enlaces documentales sin límite de registros y se deduplican
por URL. Si aparecen controles de paginación reconocidos, se produce un error
explícito, para exigir soporte del nuevo formato antes de ofrecer cobertura.
La ausencia del contenedor, encabezado o documentos técnicos causa error y no
sobrescribe el resultado anterior. `update_proyectos` vuelve a extraer el
inventario completo; no pretende mantener un cursor histórico.

## Verificación y evidencia local

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_guarena -v`

Seis pruebas correctas: agrupación/deduplicación y procedencia, fechas y geometría
sin inferencias, rechazo de navegación/formularios, paginación explícita,
redirección/dominio documental inesperados, carga mediante manifest y contrato de
actualización/licencias, y conservación del archivo ante fallo del parser.

Se ejecutó `backfill_proyectos` a través de `load_portal_adapter(load_manifest('guarena'))`
contra el sitio real: **1 registro y 13 documentos**. Evidencias locales:

- `evidence/proyectos.jsonl`: registro real, con anotación de la política compartida.
- `evidence/validation.json`: recuentos, URLs completas, limitaciones, instante de
  consulta y resultado de la comprobación documental.
- `evidence/inventory.html`: HTML completo de la consulta usada por el adaptador.
- `evidence/document-03-prefix.bin`: primeros 2048 bytes de la
  [memoria estructural](https://www.aytoguarena.es/recursos/pdf/plan-general-municipal/20230608_2022-doc-03.pdf).
  HTTP 200, `application/pdf` y firma `%PDF-` comprobados. Captura parcial: no se
  descargaron ni validaron íntegramente los 13 PDF y no se afirma lo contrario.

No se ejecutaron publicaciones, geocodificación, bases de datos ni despliegues.
Las evidencias son locales y no forman parte de los cuatro archivos fuente.
