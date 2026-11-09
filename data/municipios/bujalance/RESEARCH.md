# Bujalance (Córdoba), INE 14012

Investigación y ejecución real: 9 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, el cargador y esquema de `municipio/manifest.py`,
el registro de adaptadores y el ejemplo de Chipiona. No se modifican fuentes
compartidas ni dependencias.

## Fuentes oficiales y selección

- Inventario municipal «Normativa Municipal»:
  https://bujalance.es/ayuntamiento/ayuntamiento-documentos/
- Representación pública WordPress utilizada en la extracción:
  https://bujalance.es/wp-json/wp/v2/pages?search=pgou
  Devuelve actualmente una página, ID 7942, con `X-WP-Total: 1` y
  `X-WP-TotalPages: 1`. Su enlace canónico coincide con el inventario anterior.
- Memoria técnica comprobada y capturada íntegramente:
  https://bujalance.es/wp-content/uploads/2021/09/tr_pgoubujalance19_memoria.pdf
  HTTP 200, `application/pdf`, firma `%PDF-`, 7.875.645 bytes.
- Publicaciones oficiales localizadas para contraste del carácter del instrumento:
  https://www.juntadeandalucia.es/boja/2013/28/48 y
  https://www.juntadeandalucia.es/boja/2021/99/68 .
  No se convierten estos anuncios en proyectos adicionales.

El HTML canónico y el endpoint individual `/wp-json/wp/v2/pages/7942`
devolvieron 403 en este entorno. La consulta pública de búsqueda sí devuelve el
contenido municipal completo, incluidos los enlaces. No se usan resultados del
buscador como registros ni se recurre a credenciales.

## Unidad, procedencia y cobertura

La sección «PGOU Bujalance y Morente – Texto Refundido Junio 2019» contiene
**un instrumento con 31 enlaces únicos**, conservados como `documentos`:
actas, BOJA, registros autonómico y municipal, corrección de error material de
Ancha de Palomino 15/17, catálogo, estudio económico, estudio ambiental, fichas,
memoria, normativa y planos de información y ordenación. Morente es parte del
ámbito del mismo PGOU, no otro municipio. La corrección publicada dentro de esta
sección se conserva como documento del instrumento, sin duplicar el PGOU.
Cada enlace conserva su rótulo literal, URL, contexto de sección y URL del
inventario. Los rótulos genéricos del catálogo no se reinterpretan a partir del
nombre de archivo. El ID del instrumento es estable respecto de cambios de título.

Se excluye todo lo anterior a la cabecera del PGOU (ordenanzas y reglamentos,
incluidas «Licencias Urbanísticas» y «Procedimiento de tramitación y aprobación
de proyectos de urbanización»): son normativa, no concesiones ni proyectos
concretos. También se detiene la selección ante la siguiente cabecera h2.
No se extraen noticias ni anuncios de contratación. Licencias desactivadas.

La cobertura es **parcial**, limitada a este inventario documental consultable
actualmente: no pretende ser un registro exhaustivo de modificaciones, obras ni
licencias. No se afirma vigencia legal actual ni ejecución material. Los enlaces
antiguos `sites/default/files` y el acceso a SITU@ se conservan por procedencia;
no se ha comprobado la disponibilidad de los 31 destinos. La muestra PDF sí
verifica contenido técnico real. No se extraen geometrías de los planos.

## Fechas y paginación

«Junio 2019» forma parte del título documental, no se transforma en fecha de
acuerdo. Las fechas de publicación de BOJA no se atribuyen a acuerdos. La página
municipal rotula el pleno de subsanación como 26/09/2019, mientras el texto BOJA
2021 menciona 26/09/2020; el scraper conserva el rótulo del enlace y no resuelve
esa discrepancia inventando una fecha normalizada. Tampoco usa las fechas CMS
2021/2025 como fechas del instrumento. No genera campos fecha, fase o coordenadas;
marca `publication_ready: false` y `geometry_status: unavailable`.

El adaptador recorre todas las páginas declaradas en `X-WP-TotalPages`, comprueba
el total de elementos, detecta páginas repetidas y cambios de totales durante la
consulta. Cabecera ausente, lista vacía, sección sin memoria/normativa o paginación
incompleta provocan error antes de sustituir la salida. Una paginación incrustada
en el contenido también provoca error para evitar omitir documentos. La
actualización repite el inventario completo sin cursor de fecha ni modificación
del archivo de estado.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_bujalance -v`: cinco tests correctos.
Cubren selección y agrupación de documentos, exclusión de ordenanzas/contratación,
metadatos sin fechas ni geometría inferidas, datos inesperados, seguimiento de dos
páginas, fallos de integridad sin sobrescribir salida, manifest y licencias vacías.

Ejecución real por `load_manifest('bujalance')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir'] = 'evidence'` antes de cargar el adaptador.
Resultado: **1 registro real, 31 enlaces**, con anotación del registro compartido.
La clasificación compartida resultó desconocida (`unknown: 1`); no se modifica la
política común para forzar una categoría.

Evidencia local excluida del commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/pages-pgou-1.json`,
`evidence/document-check.json`, `evidence/pgou-memoria.pdf` y captura de la
respuesta HTML 403 `evidence/inventory.html`. El manifiesto desactiva ejecución
programada y jitter de coordenadas. No se ha publicado ni enviado nada a servicios
de producción.
