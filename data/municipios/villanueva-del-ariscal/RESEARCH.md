# Villanueva del Ariscal — Sevilla — INE 41098

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

El [portal de transparencia municipal](https://transparencia.villanuevadelariscal.es/es/)
identifica al Ayuntamiento de Villanueva del Ariscal y enlaza sus indicadores:

- [50: PGOU y planos](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00023/).
  Remite al inventario provincial `http://3web.dipusevilla.es/planeamiento/pgouvillanuevadelariscal/098PGtr.htm`.
  Advierte expresamente que el documento requiere cotejo con las correcciones de las
  aprobaciones provinciales. La consulta web de ese destino por HTTPS agotó el tiempo
  de espera; no se extrae un PGOU consolidado ni se afirma su vigencia.
- [53: modificaciones del PGOU y planes parciales](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados./).
  Dos PDF, uno de modificación y otro de situación a la publicación del portal.
  El PDF `2018_Modificacion-PGOU-1.pdf` reproduce una aprobación del 29/10/2018,
  publicada en el BOP de 22/05/2019: son fechas distintas. No se incorpora este
  inventario a la cobertura del adaptador de obras.
- [54: convenios y actuaciones urbanísticas](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00023/).
  Expone un PDF de información colectiva; no se convierte el indicador en un proyecto.
- [61: proyectos de obras públicas](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Obras-mas-importantes-de-infraestructura-que-estan-en-curso-00023/).
  **Fuente implementada**: tabla municipal de documentos técnicos de obras físicas.
- [62: obras realizadas o pendientes de ejecución](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Obras-de-infraestructura-realizadas-y-o-las-aprobadas-pendientes-de-ejecucion-00023/).
  Contiene biblioteca municipal, archivos colectivos (carril bici, escuela de música)
  e información de obras realizadas. Se documenta su existencia sin afirmar haber
  extraído ni identificado todas las intervenciones de esos archivos.

Los cinco indicadores respondieron HTTP 200 en las consultas directas con requests.
Sus HTML están en `evidence/discovery-0.html` a `discovery-4.html`, respectivamente.
La cobertura elegida es parcial y explícita: los proyectos PDF del indicador 61,
no toda la actividad urbanística, el archivo completo del BOP o una consulta de
licencias concedidas. Formularios, licitaciones y noticias no generan registros.

## Extracción y agrupación

La galería 61 tiene **dos páginas**, con 10 y 5 documentos. Se siguen los enlaces
`a[numpag]` del paginador OpenCMS, incluido
[el segundo bloque](https://transparencia.villanuevadelariscal.es/es/transparencia/indicadores-de-transparencia/indicador/Obras-mas-importantes-de-infraestructura-que-estan-en-curso-00023/?pagegalleryfiles-1-1=2).
Resultado vivo: **11 intervenciones, 14 PDF enlazados**. Cada PDF se descargó
correctamente y se contrastaron las primeras tres páginas con `pdftotext`, ya
instalado. La descarga y conversión son investigación local, no dependencias del
adaptador. Las capturas completas y sus extractos están en `evidence/`.

Intervenciones identificadas:

| Intervención | Documentos | Identificación contrastada |
| --- | ---: | --- |
| Parques y jardines, Supera V | 1 | Modificado de reparación y conservación |
| Ascensor, Supera V | 1 | Adecuación a normativa de edificios e instalaciones públicas; Plaza de España 1 |
| Viales y espacios públicos, Supera V | 1 | Proyecto de reparación y conservación |
| CEIP Manuel Castro Orellana, Supera V | 1 | Reparación y conservación del colegio |
| Viarios, Supera III | 1 | Proyecto completo subsanado; índice identifica Supera III |
| Instalaciones deportivas en avenida de los Niños, Supera IV | 2 | Piscina: proyecto completo y modificado de reinversión de baja |
| Viarios, reinversión de baja Supera IV | 1 | Portada identifica expresamente Supera IV |
| Ludoteca en avenida de los Niños | 1 | Rehabilitación de edificio anexo al recinto deportivo |
| Accesos al CEIP, Supera IV | 2 | Proyecto y reinversión de baja |
| Alumbrado público, Supera IV | 2 | Proyecto reformulado y reinversión de baja |
| Plaza Rafael Alberti, PFOEA 2015 | 1 | Proyecto básico y de ejecución de reforma de viarios |

Los grupos reúnen documentos por intervención y programa, sin afirmar identidad
de expediente administrativo. Los proyectos de reinversión conservan el título
literal municipal y su URL dentro de `documentos`. Los proyectos Supera V del
colegio y viarios permanecen separados de los programas anteriores. El archivo
`E.4.61-Plan-Supera-III.rar` queda en `excluded_documents` con URL y motivo: es un
paquete colectivo sin descomposición verificada; no es una actuación sintética ni
un decimoquinto proyecto. El enlace se conserva también en `source_urls`.

Los nombres de archivo revisados identifican los grupos, pero no crean registros
precargados: solo se emiten documentos presentes en las respuestas vivas. Una
adición no revisada, un cambio de procedencia, ausencia de proyectos o un fallo de
paginación provoca error antes de sobrescribir la salida. El límite defensivo de
100 páginas provoca error, nunca una salida truncada. `update_proyectos` vuelve a
leer el inventario completo; no mantiene un cursor de fechas inventadas.

## Semántica y limitaciones

El rótulo municipal «en curso» no acredita que las obras históricas sigan en
construcción hoy. Los PDF revisados incluyen documentos de 2015–2017. Las fechas
de firma técnica no son acuerdos, aprobaciones ni fechas de publicación del
portal: esos campos quedan nulos, sin `fase` inferida. Sin coordenadas, polígonos
ni geocodificación ficticia; `geometry_status: unavailable` y
`publication_ready: false` en todos los registros. Las denominaciones agrupadas
se basan en las portadas, mientras cada documento conserva su etiqueta original.

Licencias desactivadas: no se ha verificado un inventario público de concesiones.
El manifest identifica municipio/provincia/INE, desactiva el calendario y el jitter.
La cobertura no implica exhaustividad histórica ni vigencia urbanística actual.

## Validación reproducible

Pruebas offline, sin archivos de evidencia como fixtures:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villanueva_del_ariscal -v
```

Siete pruebas correctas: agrupación sin duplicados, separación de programas,
rechazo de formularios y documentos nuevos, recorrido de ambas páginas, fallo de
paginación sin sobrescritura parcial, procedencia y manifest/licencias desactivadas.

Extracción real ejecutada con
`VillanuevaDelAriscalAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
configurando `capture_dir: evidence`. Resultado: 11 registros, 14 documentos,
2 páginas HTTP 200 y 1 archivo colectivo excluido expresamente.
`evidence/validation.json` contiene recuentos, URLs, capturas y limitaciones;
`evidence/parser-tests.txt` contiene la salida de pruebas. Evidencia local ignorada
por Git, sin cambios en fuentes compartidas, dependencias, publicación o despliegue.
