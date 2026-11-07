# Betanzos — INE 15009, A Coruña, Galicia

Investigación y ejecución real: 7 de noviembre de 2026. Adaptador exclusivo para Betanzos, conforme al contrato de `municipio/adapters/portal.py` y al esquema de `municipio/manifest.py`; consultados los ejemplos Chipiona, Hernani y Manlleu.

## Fuentes descubiertas y alcance

- Inventario municipal de Urbanismo: https://concello.betanzos.es/urbanismo/ . Sus pestañas contienen información catastral, ayudas, formularios, referencias a NNSS y PEPOCH y un enlace al expediente documental del PXOM. El adaptador descubre ese enlace en las pestañas, sin devolver la página general como proyecto.
- Ficha municipal extraída: https://concello.betanzos.es/portfolio-items/plan-xeral-de-ordenacion-urbana-do-concello-de-betanzos/ . Identifica la revisión del Plan xeral de ordenación municipal de Betanzos, documento para aprobación inicial de julio de 2021. La extracción en vivo produjo **un instrumento con 13 enlaces documentales**: anuncio DOG, certificado del Pleno, índice PDF y diez carpetas de documentación técnica. Todos se agrupan en el instrumento; se conservan sus etiquetas, enlaces y página municipal de procedencia. Las carpetas externas de Google Drive son enlaces publicados por el Concello, no una afirmación de que se hayan descargado o enumerado todos sus archivos. El visor informativo no proporciona geometría verificada para el registro.
- Inventario de transparencia: https://sede.betanzos.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html . Enlaza al antiguo inventario autonómico `http://www.planeamentourbanistico.xunta.es/siotuga/inventario?inv=1&idconcello=15009` y enumera planes antifraude, subvenciones y económico financiero. No se convierten en actuaciones físicas. La etiqueta PXOM de ese enlace no prueba aprobación definitiva.
- https://concello.betanzos.es/plans-e-programas/ contiene un plan normativo, fuera del alcance de proyectos urbanísticos.

Cobertura deliberadamente parcial: **inventario documental municipal del PXOM**, no todas las obras, instrumentos ni licencias del municipio. NNSS y PEPOCH mencionados en Urbanismo no se transforman en registros sin revisar sus expedientes; tampoco se recorre el tablón general, noticias ni contratación. La portada municipal muestra además una entrada PEPOCH de aprobación inicial: queda fuera de este adaptador, que no afirma exhaustividad. La ficha PXOM de 2021 sigue enlazada desde Urbanismo; ello no acredita que sea la última versión del instrumento. No se afirma vigencia ni fase actual. No se extraen noticias sobre posibles acuerdos posteriores como si fuesen documentos del expediente.

Las dos páginas recorridas no presentan paginación de este inventario. Se procesan todos los enlaces PXOM distintos descubiertos en las pestañas y todos los enlaces documentales admitidos dentro de cada ficha. La detección de navegación paginada o carga adicional provoca un error explícito, no un corte silencioso. No se limita el número de resultados. La ausencia del enlace, del instrumento identificado o de PDFs municipales también provoca error.

## Fechas y procedencia

La ficha declara acuerdo del Pleno de **15 de septiembre de 2021** y publicación del anuncio en DOG de **20 de octubre de 2021**. Se extraen por contexto como `fecha_acuerdo` y `fecha_publicacion`; esta última lleva una etiqueta que indica que es publicación del anuncio, no fecha del CMS. No se deducen fechas de los directorios de subida ni del mes de redacción. No se genera `fecha_aprob`, fecha de concesión, fase actual ni coordenadas. Todos los registros llevan `publication_ready: false` y `geometry_status: unavailable`.

Se descargó y comprobó el documento municipal https://concello.betanzos.es/wp-content/uploads/2021/10/AnuncioL109-141021-0001_gl.pdf : HTTP 200, `application/pdf`, firma `%PDF-`, 440094 bytes. Su texto (comprobado con `pdftotext`) confirma las fechas anteriores e identifica el expediente 2018/X999/000210. Este identificador se documenta aquí como comprobación del PDF; el parser HTML no lo inventa ni lo inserta sin extraerlo. La fecha de firma del anuncio (7 de octubre) es distinta del acuerdo y de su publicación. El anuncio trata la aprobación inicial y suspensión de licencias; no es un registro de licencias concedidas.

Se excluyen formularios de alegaciones, enlaces sociales, documentos ajenos al cuerpo de la ficha y PDFs externos no municipales. Cada documento retenido incluye `provenance_url`. Las carpetas de Drive conservan únicamente la autoridad de su enlace desde la ficha municipal, no una validación independiente de su contenido.

## Validación reproducible y evidencias locales

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_betanzos -v
```

Siete pruebas correctas: descubrimiento y deduplicación, agrupación/procedencia, fechas separadas y ausentes, rechazo de paginación, rechazo de fuente vacía o sin documentos, actualización reproducible y licencias desactivadas.

Ejecución real directa de `BetanzosAyuntamientoAdapter('betanzos', config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 13 enlaces documentales**. No se usan bases de datos, geocodificación ni publicación. La actualización vuelve a extraer el inventario completo; no presupone fechas de modificación fiables ni un cursor incremental.

Evidencias locales no destinadas al commit:

- `evidence/proyectos.jsonl`: extracción real.
- `evidence/validation.json`: `live_records`, URLs, limitaciones, resultado de pruebas y comprobación del PDF.
- `evidence/95065bcc9aca20db.html.gz`: captura de Urbanismo.
- `evidence/a21fa405ee94e524.html.gz`: captura de la ficha PXOM.
- `evidence/pxom-dog.pdf`: anuncio DOG completo comprobado.
- `evidence/source-2.html.gz` y `evidence/plans.html.gz`: fuentes complementarias investigadas.

El espacio disponible se agotó durante la primera captura PDF; se conservaron las capturas iniciales comprimidas en `/tmp` y se recuperó espacio únicamente de las capturas propias. La extracción final y la descarga PDF se completaron correctamente. No queda una evidencia PDF vacía.

El manifest desactiva `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing`.
