# Arboleas — INE 04017, Almería

Investigación y extracción real: 9 de noviembre de 2026. Adaptador exclusivo del
Ayuntamiento de Arboleas; sin cambios compartidos ni dependencias nuevas.

## Fuentes descubiertas

- Portal municipal: https://www.arboleas.org/ . Identifica Ayuntamiento, domicilio
  Plaza de España, 1, 04660 Arboleas (Almería), y enlaza la sede electrónica.
- Inventario oficial de planeamiento:
  https://www.arboleas.org/index.php?option=com_content&view=section&id=16&Itemid=393&lang=es
- Sede https://arboleas.sedelectronica.es/info.0 : contiene trámites de solicitud
  de licencia y declaración responsable. No es un registro de licencias concedidas
  y no se utiliza como fuente de registros.
- La portada también anuncia Obras Municipales, noticias y tablón. Quedan fuera
  de esta implementación: no se convierten anuncios de contratación o noticias
  genéricas en proyectos.

La sección de planeamiento enumera ocho categorías y sus cantidades de fichas:
NNSS 1997 (80, 5), Mod. Puntual 2000 (81, 2), Mod. Puntual 2001 (82, 3), adaptación
PGOU a LOUA (83, 1), Innovación 12 (84, 1), Innovación 13 (87, 14), Revisión Parcial
del PGOU (89, 4), Innovación 14 (94, 15). El menú lateral conserva además un enlace
obsoleto a categoría 88 que devuelve HTTP 404. El scraper utiliza los enlaces del
inventario central, no ese menú.

El descubrimiento de categorías y fichas es dinámico. Cada categoría se recorre
por su tabla y todos los enlaces de paginación; se deduplican fichas por identidad
Joomla. La cantidad obtenida debe coincidir con la publicada en la sección.
Errores HTTP, contenedores ausentes, cantidades incompletas, artículos sin
adjuntos o paginación de artículo no soportada provocan error antes de sustituir
el resultado. El límite de seguridad de 500 páginas también provoca error,
nunca devuelve una extracción truncada. La ejecución observada no necesitó
páginas adicionales: la categoría mayor tenía 15 fichas.

## Unidad de registro y procedencia

Resultado real: **7 instrumentos, 45 fichas y 95 enlaces documentales**:

| Instrumento | Fichas | Enlaces |
| --- | ---: | ---: |
| NNSS 1997 | 5 | 44 |
| Mod. Puntual 2000 | 2 | 6 |
| Mod. Puntual 2001 | 3 | 10 |
| Adap PGOU a la LOUA | 1 | 1 |
| Innovación 12 (2012) | 1 | 1 |
| Innovación 13 (2012) | 14 | 14 |
| Innovación 14, incluida Revisión Parcial | 19 | 19 |

Las memorias, planos, normativa y publicaciones administrativas de un mismo
instrumento se agrupan. Cada adjunto conserva título, URL y `source_page` de su
ficha municipal; cada registro conserva todas sus categorías y fichas de origen.
No se mezclan planos de innovaciones distintas ni se crea un proyecto por plano.

La categoría 89 se agrupa con 94 porque la portada de su memoria dice
«INNOVACION Nº 14 DEL P.G.O.U. DE ARBOLEAS / REVISION PARCIAL DEL P.G.O.U.»:
https://www.arboleas.org/images/pdf/Revisionparcial/memoria%20revisin%20parcial.pdf
(ficha municipal 375). La portada fecha la redacción en marzo de 2014; eso no se
interpreta como acuerdo. Se capturó el PDF completo, HTTP 200 y firma `%PDF-`,
y se examinó su inicio mediante pdftotext. También se descargó la resolución
vinculada en la ficha 403, HTTP 200 y firma PDF; no ofrecía texto en las primeras
páginas mediante pdftotext, por lo que no se dedujo fecha ni alcance de aprobación.

Los enlaces municipales a `/images/` y los históricos de la Junta con ruta
`/viviendayordenaciondelterritorio/iws/pua_ext/ALMERIA/04017/` se conservan tal
como están publicados, escapando espacios. No se confunde el botón PDF de Joomla
con un documento técnico. No se comprueba la descarga de los 95 adjuntos; los
enlaces históricos HTTP de la Junta pueden estar obsoletos. La evidencia contiene
los dos PDF de muestra, capturas HTML y trazabilidad URL/archivo de la ejecución.

## Límites semánticos y cobertura

Cobertura parcial: inventario documental de planeamiento expuesto actualmente
en la web, con material histórico y distintas versiones/fases de tramitación.
No es un inventario completo de obras públicas ni de expedientes del municipio;
no acredita vigencia jurídica actual ni aprobación íntegra de un instrumento.
En particular la presencia de una resolución no permite afirmar que todo el
ámbito de la Innovación 14 haya quedado aprobado.

No se extraen fechas de publicación, acuerdo o aprobación de los documentos.
Los años de los títulos, nombres de archivo y fechas de redacción no alimentan
ningún campo de fecha. La descripción de las NNSS contiene incluso «14-07-1197»;
no se corrige silenciosamente ni se usa como fecha. No hay fase deducida del tipo,
coordenadas ni geometrías inventadas. `publication_ready=false` y
`geometry_status=unavailable`. Licencias, programación y jitter desactivados.
La actualización vuelve a recorrer el inventario completo, sin un filtro temporal
que omita documentos históricos añadidos recientemente.

## Verificación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_arboleas -v` (8 pruebas offline).
Comprueban alcance de contenedores, exclusión de solicitudes, adjuntos y enlaces
históricos del municipio correcto, codificación de URLs, procedencia, agrupación,
ausencia de fechas/coordenadas inferidas, segunda página y ciclos de paginación,
fallo ante conteo incompleto sin sustituir salida, manifiesto y licencias vacías.
Las muestras HTML de los tests son sintéticas y no se emiten como registros reales.

Extracción real: instanciar `ArboleasAyuntamientoAdapter('arboleas',
config={'capture_dir': 'evidence/live-captures'})` e invocar
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se ejecutó con éxito.
`evidence/validation.json` guarda `live_records`, `source_urls`, conteos, capturas,
fecha UTC y limitaciones. Evidencia local excluida de los cuatro archivos fuente.
No se ejecutaron publicación, sincronización ni servicios externos privados.
