# Ermua — INE 48034, Bizkaia

Verificación directa: 2026-11-07. Adaptador exclusivo para Ermua.

## Descubrimiento y fuentes

La unidad municipal de [Urbanismo](https://www.ermua.eus/es/ayuntamiento/organizacion-administrativa/area-urbanismo-sostenibilidad/urbanismo)
remite a [Planes municipales](https://www.ermua.eus/es/ayuntamiento/accion-gobierno/planes-municipales).
Se consulta este inventario en cada ejecución, tomando los enlaces del apartado
Urbanismo cuyo título sea Plan General o Plan Especial. No se usa una noticia ni
una lista codificada de expedientes. Fuentes actuales, todas HTTP 200:

- [PGOU y modificaciones](https://www.ermua.eus/es/ayuntamiento/accion-gobierno/planes-municipales/plan-general-ordenacion-urbana).
- [Protección y Conservación del Casco Histórico](https://www.ermua.eus/es/ayuntamiento/accion-gobierno/planes-municipales/plan-especial-proteccion-casco-historico).
- [Plan Especial Senda Verde](https://www.ermua.eus/es/ayuntamiento/accion-gobierno/planes-municipales/plan-especial-senda-verde).

## Extracción y semántica

Cinco registros reales; 95 asociaciones documentales:
PGOU (34), modificación 1ª Ureta (13), modificación 3ª IDESA (4),
Casco Histórico (16), Senda Verde (28). Los planos y tomos no generan registros
independientes. Se retienen también las sesiones plenarias enlazadas con su tipo;
no se ha extraído su contenido. Los documentos incluyen URL de la página que los
publica. IDs deterministas por URL del instrumento y número de modificación.

La página declara aprobado el PGOU en 2015 y aprobaciones definitivas de las
modificaciones en 2018 y 2025: solo se extrae `anio_aprobacion`. No se inventa
el día 1 de enero. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob`
son nulas. Los meses en nombres de PDFs son versiones documentales, no fechas
acreditadas de acuerdos. Los dos planes especiales se documentan sin atribuirles
una aprobación ni fase que la página no declara.

El grupo documental general del PGOU contiene planos actualizados en 2018 y 2025,
según sus propios enlaces: es la colección actual municipal, no una copia íntegra
de la versión original de 2015. Algunos planos se enlazan también bajo su
modificación; se conserva esta procedencia en ambos instrumentos. No se inventa
una segunda modificación para rellenar el salto entre 1ª y 3ª.

## Cobertura y límites

Cobertura parcial de instrumentos urbanísticos publicados en ese inventario.
Se excluyen planes estratégicos generales, accesibilidad, movilidad, deportes,
políticas sociales, formularios, noticias y anuncios de contratación. No es un
registro de todas las obras o del histórico completo de expedientes. No se ha
verificado un inventario público de licencias concedidas; licencias deshabilitadas.

Las páginas actuales son documentos HTML completos con secciones desplegables,
sin paginación. Se recorren todos sus enlaces documentales, sin límite de registros
ni corte por páginas. Si aparece paginación, desaparece el contenido esperado o un
instrumento carece de documentos, se falla antes de reemplazar la salida. Las
etiquetas de modificaciones con formato cambiado requieren revisión explícita.
La actualización refresca la instantánea completa; no usa marcas temporales ni
modifica el archivo de estado. La salida vacía requiere revisión, no se acepta.

## Geometría

`geometry_status: unavailable`. Las fuentes utilizadas enlazan planos PDF,
sin geometría vectorial vinculada por expediente. No se vectorizan planos ni
se usan coordenadas del centro del municipio. El catálogo oficial de
[planeamiento de Ermua](https://datos.gob.es/es/catalogo/l02000048-planeamiento-urbanistico-ermua1)
ofrece información agregada/orientativa; no se ha verificado una correspondencia
geométrica con estos cinco instrumentos. Geometría, latitud y longitud nulas;
`publication_ready: false`, `geocode.jitter_missing: false`.

## Comprobaciones reproducibles

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_ermua -v`: cuatro pruebas de agrupación,
estabilidad de IDs, fechas, procedencia, exclusión de contenido no urbanístico,
fallos por paginación/cambio de estructura y ejecución del adaptador.
Extracción real mediante `ErmuaAyuntamientoAdapter.backfill_proyectos`:
5 registros. Se verificó un PDF representativo por instrumento: cinco respuestas
HTTP 200 con MIME PDF y firma `%PDF`; no se verificaron todos los PDFs ni se
interpretaron sus contenidos. La primera solicitud con User-Agent de requests
recibió 403; la extracción con User-Agent de navegador identificando el adaptador
funcionó, sin autenticación.

Evidencia local en `evidence/`: `proyectos.jsonl`, `validation.json`, capturas HTML,
resultado de ejecución y comprobaciones de documentos. No forma parte de los cuatro
archivos fuente. Programación deshabilitada; sin cambios de dependencias ni fuentes
compartidas, sin publicación ni operaciones de base de datos.
