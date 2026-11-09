# La Luisiana (Sevilla), INE 41056

Investigación y extracción real: 9 de noviembre de 2026. Adaptador único
`municipio.adapters.la_luisiana:LaLuisianaAyuntamientoAdapter`.

## Fuente oficial y cobertura

El Portal de Transparencia del Ayuntamiento publica un inventario documental:

https://transparencia.laluisiana.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00066

Bajo el encabezado «PLAN GENERAL DE ORDENACIÓN URBANA DE LA LUISIANA» aparecen
cuatro galerías del instrumento: PGOU, PLANOS DE INFORMACIÓN, PLANOS DE ORDENACIÓN
y PLANOS ESTUDIO DE INUNDABILIDAD. El scraper lee sus tablas, conserva los títulos
literales, grupo documental, enlaces PDF y páginas donde aparece cada documento.
No transforma memorias, planos o el catálogo de bienes en proyectos separados.

La galería de inundabilidad tiene dos páginas. Se recorren todos los enlaces de
paginación de las cuatro galerías, normalizando fragmentos y página 1, con
conjunto de visitados y deduplicación por URL del documento. La segunda página es:

https://transparencia.laluisiana.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00066?pagegalleryfiles-4-1=2

Resultado vivo: **1 instrumento PGOU, 38 documentos únicos, 2 páginas**.
Distribución: PGOU 9, información 9, ordenación 8, inundabilidad 12 (10 + 2).
La fuente municipal sirve ambos HTML con HTTP 200. Una muestra documental
`PGOU/05-Estudio-Economico-y-Programa.PDF` respondió HTTP 200,
`application/pdf` y firma `%PDF-`. Se conservaron solo sus primeros 1024 bytes;
no se descargaron masivamente los PDF ni se verificó todo su contenido.

## Límites y semántica

Cobertura deliberadamente parcial: solo el PGOU publicado. En la misma página
se descubrió una quinta galería «PROYECTOS DE ACTUACIÓN» con cinco enlaces,
algunos titulados solo con nombres de promotores. Se excluye de este adaptador:
no se han inspeccionado sus documentos para establecer proyectos distintos o
posibles relaciones entre versiones, promotores y anexos. No se afirma que
esos documentos sean concesiones ni se generan registros a partir de sus nombres.
No se recorren noticias, contratación, formularios ni otros inventarios municipales.

El inventario no proporciona fechas inequívocas de publicación o acuerdo del PGOU.
La fecha incluida en el título de un documento de subsanación se conserva como
parte del título, sin convertirla en fecha de aprobación del instrumento.
No se determina vigencia, fase administrativa, concesión de licencia ni fecha de
aprobación. No hay coordenadas, centroides ni geometrías inventadas.
`publication_ready: false`, `geometry_status: unavailable`.
Licencias, ejecución programada y jitter están desactivados en el manifest.

Un cambio del encabezado, ausencia de alguna galería, tabla vacía, enlaces fuera
de los directorios documentales revisados, redirección inesperada o fallo HTTP
aborta la extracción. El límite de seguridad de 100 páginas también provoca
error, nunca una salida truncada. La salida se sustituye solo al completar el
recorrido. La actualización vuelve a leer el inventario completo; no mantiene
historial de documentos retirados. Una ampliación de cobertura requiere revisar
y adaptar explícitamente el parser.

## Verificación y evidencia local

Primero se inspeccionaron `municipio/adapters/portal.py`, el cargador de manifests,
el registro de adaptadores y los ejemplos Chipiona y Hernani. No se cambian
fuentes compartidas ni dependencias.

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_luisiana -v`: **6 correctas**. Cubren
selección documental, rechazo de inventarios vacíos o alterados, URLs ajenas,
paginación completa, deduplicación, agrupación en un instrumento, ausencia de
fechas inferidas, licencias desactivadas y conservación de salida ante fallo de
una página posterior.

La ejecución real usó `load_manifest('la-luisiana')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir'] = 'evidence'`. No necesita credenciales,
geocodificación, publicación ni bases de datos.

Evidencia local sin commit:

- `evidence/proyectos.jsonl`: registro real con los 38 enlaces agrupados.
- `evidence/validation.json`: número de registros, fuentes, limitaciones,
  resultado del adaptador y comprobación de la muestra PDF.
- `evidence/live-inventory-1.html`, `evidence/live-inventory-2.html`: capturas
  tomadas por el propio adaptador durante la ejecución real.
- `evidence/inventory.html`, `evidence/inventory-page2.html`: capturas exploratorias.
- `evidence/sample-pdf-prefix.bin`: inicio de la muestra PDF.
