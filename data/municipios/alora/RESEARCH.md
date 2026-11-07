# Álora — INE 29012, Málaga

Investigación y ejecución real: 7 de noviembre de 2026. Se revisaron el contrato
`municipio/adapters/portal.py`, `municipio/manifest.py`, el cargador del registro
y los ejemplos de Chipiona y Manlleu antes de implementar el adaptador.

## Inventario oficial actual

La portada efectiva es [Inicio](https://www.alora.es/Inicio/). La raíz del dominio
contiene una redirección HTML a esa página. Su menú «Áreas de gobierno / Urbanismo»
enlaza dos páginas documentales y un grupo de tres documentos de Mirasierra:

- [Normas Subsidiarias](https://www.alora.es/Ayuntamiento/nnss/): un instrumento
  con siete enlaces a PDF: alineaciones, calificación, clasificación, diseminados,
  infraestructuras, memorias y normas urbanísticas. No siete proyectos distintos.
  No se atribuye fecha de aprobación o vigencia a partir de su mera publicación.
- [Avance del PGOM](https://www.alora.es/ayuntamiento/pgom/): un instrumento con
  dos documentos, «Borrador del plan (EAE) Álora» y «Comunicación de validez del
  documento de alcance del estudio ambiental estratégico de la revisión del plan
  general de ordenación urbanística de Álora». La narración municipal declara
  que el acuerdo del pleno de **11/Jul/24**, referenciado como publicado en el
  **BOP 12/Agos/24**, consideró el borrador del plan como avance del PGOM. Por eso
  `fecha_acuerdo=2024-07-11`, `fecha_publicacion=2024-08-12` y
  `medio_publicacion=BOP (referenciado en la página municipal)`. No se afirma
  haber consultado el ejemplar del BOP, ni que esa sea la fecha de publicación
  en la web. La fase es «avance»; no aprobación definitiva ni aprobación de obra.
- «Estudio detalle Calle Mirasierra», publicado como grupo en el menú: un
  instrumento con [Anexo](https://www.alora.es/Ayuntamiento/Informacion/mirasierra/ANEXO.pdf),
  [Planos](https://www.alora.es/Ayuntamiento/Informacion/mirasierra/PLANOS.pdf) y
  [Memoria Expositiva](https://www.alora.es/Ayuntamiento/Informacion/mirasierra/MEMORIA_EXPOSITIVA.pdf).
  El nombre procede del grupo municipal, no de una inferencia sobre nombres de
  archivos. Sin fase ni fecha de acuerdo verificadas. Una descarga exploratoria
  de la memoria devolvió HTTP 200, application/pdf y 1.034.227 bytes. Su extracción
  con pdftotext no produjo texto utilizable (documento escaneado); no se infieren
  acuerdos, fechas ni contenido parcelario de ese documento.

También se inspeccionó la [antigua página del PGOU](https://www.alora.es/ayuntamiento/pgou/),
que ofrece archivos RAR de aprobación inicial y evaluación ambiental estratégica.
No está enlazada como página actual de planeamiento en el menú observado. El PGOM
explica que reutiliza el borrador del PGOU: no se crea otro registro de plan general
por esos paquetes históricos. No se descargaron los RAR de 777 y 82 MB.

Los modelos de declaración responsable/comunicación de obras, el registro de
demandantes de vivienda y las noticias municipales se excluyen. No se verificó
un registro público de licencias concedidas: `licencias.enabled=false`.

## Extracción y límites

El adaptador descubre los enlaces PGOM/NNSS y el grupo Mirasierra en la portada,
recorre ambas páginas y conserva las etiquetas, URL documental y página de origen.
Agrupa y elimina enlaces duplicados dentro de cada instrumento. Los identificadores
son estables por instrumento, sin depender del orden ni del contenido del menú.
Los documentos de distintas carpetas no se mezclan. Si faltan el menú esperado,
el encabezado del instrumento o sus enlaces documentales, falla explícitamente.
Solo acepta URL HTTPS del dominio municipal. Los HTML se leen con límite de 2 MB.
El sitio ASP tiene codificación cp1252 y algunos bytes inválidos en el menú común;
se sustituyen esos bytes, manteniendo comprobaciones de los encabezados y enlaces.

No se observó paginación en estas tres fuentes documentales. Son páginas estáticas,
no una consulta de expedientes paginada; el parser rechaza indicadores de paginación
reconocibles en lugar de devolver solo la primera página. No se recorre el archivo
de noticias, los plenos históricos ni contratación. La cobertura es parcial del
inventario documental enlazado actualmente, no un histórico exhaustivo ni una
certificación de vigencia. Una actualización reconstruye la instantánea completa.

No se inventan fechas, coordenadas ni concesiones. No se usa la fecha del pie de
página o la fecha de descarga como fecha del instrumento. `publication_ready=false`,
`geometry_status=unavailable`, `schedule.enabled=false`, `geocode.jitter_missing=false`.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_alora -v
```

Cinco pruebas offline: agrupación y exclusiones, semántica de fechas, aislamiento y
deduplicación documental, rechazo de contenido vacío/externo/paginado, y carga por
manifest/registro con actualización estable y licencias desactivadas.

Ejecución real mediante `load_manifest('alora')`, `load_portal_adapter(manifest)` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir']='evidence'`. Resultado: **3 registros y 12
documentos**. La anotación compartida de entidades conserva los registros como
`unknown`; no se interpreta como aprobación editorial o autorización de publicación.

Evidencia local, fuera de los cuatro archivos fuente entregables:
`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de las tres
páginas y prefijos binarios de documentos. Los enlaces PDF se comprueban por HTTP,
Content-Type y firma en los primeros 1024 bytes, cerrando la respuesta sin descargar
los grandes planos completos. Es una comprobación de accesibilidad y formato,
no una validación íntegra del contenido técnico. Once enlaces devolvieron HTTP 206,
application/pdf y firma PDF válida. El enlace `infraestructuras.pdf` devolvió HTTP
200 con HTML, sin firma PDF: se conserva por su procedencia del inventario, sin
afirmar que la descarga esté disponible. Esta incidencia consta en validation.json.
No se usaron bases de datos,
credenciales, despliegues ni publicación.
