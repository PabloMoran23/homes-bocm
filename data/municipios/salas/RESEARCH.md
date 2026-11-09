# Salas (Asturias), INE 33059

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuentes oficiales descubiertas

- https://www.ayto-salas.es/pgo — inventario documental municipal del Plan
  General de Ordenación Urbana (PGOU). Fuente implementada: 32 enlaces a la
  biblioteca documental municipal, con memoria, normativa y planos.
- https://www.ayto-salas.es/planeamiento-urban%C3%ADstico — describe el Plan
  Parcial del Polígono Industrial Nonaya Este, SURI-SLS-01, como documentación
  en redacción. Es una página narrativa distinta del paquete PGO; no se incorpora
  como otra versión del PGO ni se convierte en obra ejecutada.
- https://www.ayto-salas.es/mapa-web — navegación municipal explorada para
  localizar las secciones; no constituye un registro de proyectos.
- https://ayto-salas.sedelectronica.es/info.0 — catálogo público localizado en
  búsqueda, con solicitudes de licencia y declaraciones responsables. No se ha
  acreditado un registro público de concesiones. Licencias desactivadas.

Las tres páginas del dominio municipal se capturaron en `evidence/`. La sede
se descubrió por búsqueda; no se implementó su catálogo de trámites.

## Unidad y procedencia

El adaptador obtiene el HTML actual de `/pgo`; exige un único bloque editorial
`.journal-content-article .detalle` que identifique el PGOU y contenga enlaces
de Memoria y Normativa. Agrupa **los 32 documentos en un instrumento**, con ID
estable `salas-proy-pgo`. Conserva el título de cada enlace y su URL completa,
incluidos UUID y grupo de la biblioteca, además de `source_url`. Los mapas de
Salas, Cornellana y La Espina son documentos del mismo instrumento, no obras
independientes. Enlaces repetidos al mismo UUID se deduplican; documentos con
igual título y distinto UUID se retienen.

No hay paginación observable en el inventario consultado. Se recorren todos los
enlaces del bloque sin límites de registros; si aparecen controles de paginación,
enlaces de siguiente página o parámetros de página conocidos, el adaptador falla
para exigir revisión. No se implementa un rastreador general del portal.

Se comprobaron en vivo Memoria y Normativa: HTTP 200, tipo
`application/pdf;charset=UTF-8` y cabecera `%PDF-`. Se guardaron únicamente sus
primeros 2048 bytes en `memoria-prefix.bin` y `normativa-prefix.bin`. No se han
descargado ni interpretado todos los planos; conservar un enlace no certifica
la integridad de su contenido binario.

## Fechas, vigencia y cobertura parcial

La página documental no publica fechas de acuerdo, aprobación o publicación del
paquete. Todas quedan nulas, igual que la fase. La otra página de planeamiento
distingue un acuerdo de aprobación del texto refundido y su publicación en BOPA,
pero no demuestra que los 32 ficheros sean exactamente ese texto refundido.
Por ello no se trasladan esas fechas al registro ni se afirma su vigencia actual.
La fecha de ejecución tampoco se utiliza como fecha del instrumento.

Cobertura limitada al paquete PGO publicado: no es un inventario completo de
modificaciones, instrumentos de desarrollo, Nonaya Este, obras o concesiones.
No se extraen noticias, anuncios de contratación ni formularios como proyectos.
No se inventan coordenadas: `lat`, `lon` y `geometry` nulos,
`geometry_status: unavailable`, `publication_ready: false`. El manifest identifica
Salas, Asturias, `codigo_ine: '33059'`; desactiva programación, jitter y licencias.

## Verificación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_salas -v`, **7 correctas**. Cubren agrupación
y deduplicación, conservación de más de 50 documentos, exclusión de navegación,
metadatos desconocidos, fallos de estructura y procedencia, paginación, escritura
y actualización de snapshots, licencias desactivadas y manifest.

Extracción real con `SalasAyuntamientoAdapter(config={'capture_dir': 'evidence'})`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro y 32 enlaces**.
`evidence/validation.json` recoge conteo, URLs, comprobaciones PDF y limitaciones;
`evidence/pgo.html` procede de esa ejecución real. Evidencia exclusivamente local,
fuera de los cuatro archivos fuente solicitados. No se ejecutaron pasos de
publicación, bases de datos ni geocodificación.
