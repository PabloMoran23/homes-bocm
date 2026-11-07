# Sonseca — Toledo — INE 45163

Investigación y extracción real: 7 de noviembre de 2026.

## Fuente oficial y descubrimiento

La [web municipal](https://www.sonseca.es/) enlaza su [inventario de documentos](https://www.sonseca.es/documentos/), la sede electrónica y transparencia. El inventario contiene ordenanzas, normativa y solicitudes; dentro de la sección «Ordenanzas» hay una tarjeta específica titulada **NORMAS SUBSIDIARIAS DE PLANEAMIENTO URBANÍSTICO DE SONSECA**. Aunque esté situada junto a ordenanzas fiscales, es un instrumento de planeamiento real y su documento lo confirma.

Documento enlazado:
https://sonseca.es/wp-content/uploads/2021/03/upload_NORMAS-SUBSIDIARIAS-DE-SONSECA.pdf

Verificación en vivo: HTTP 200, application/pdf, firma `%PDF-1.4`, 2.808.309 bytes, 118 páginas. La portada escaneada dice «Sonseca. Normas Subsidiarias de Planeamiento Urbanístico. 1990». Se guardó el PDF completo y una imagen de la portada en evidencia. `pdftotext` no recuperó texto de las primeras cinco páginas: no se pretende haber interpretado todo el documento mediante OCR.

También se localizó la [página de plenos](https://www.sonseca.es/plenos/), con órdenes del día que mencionan modificaciones de las NNSS. Un punto de un orden del día no demuestra su aprobación: no se extrae como acuerdo ni como instrumento adicional sin verificar su documentación. El buscador también localizó documentación regional sobre la modificación nº 11; esta implementación no integra el registro regional ni afirma cubrir las modificaciones del instrumento base. No utiliza noticias ni contratación para generar proyectos.

## Alcance y semántica

Resultado real: **1 registro**, las NNSS, procedente de una tarjeta municipal con enlace documental. No se fija un registro precargado: el adaptador vuelve a leer el inventario y descarga el documento en cada extracción. El registro conserva la URL del inventario y todos los enlaces PDF del mismo instrumento, agrupados y sin duplicados; incluye URL final, tipo de contenido, tamaño y SHA-256 del documento. El identificador estable depende del nombre normalizado del instrumento, no de la ruta temporal de carga.

Cobertura parcial del inventario municipal actual, no un histórico exhaustivo de planeamiento, modificaciones, obras o licencias concedidas. No se afirma que las NNSS estén plenamente vigentes ni que el PDF reúna todas las modificaciones posteriores. La selección está delimitada a las NNSS identificadas: no intenta convertir cualquier enlace del inventario en un proyecto.

La página verificada es estática, sin paginación observada. Si aparecen controles de paginación reconocidos, el adaptador falla expresamente para evitar truncar resultados; también falla si desaparece el instrumento, su enlace o la firma PDF, si cambia el origen mediante redirección, o si la respuesta supera el límite de lectura. No hay límite silencioso de registros.

Las fechas `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob`, la fase y la geometría quedan nulas. El año de portada, la creación técnica del PDF y `/2021/03/` no se convierten en fechas de acuerdo/aprobación/publicación. `publication_ready=false`, `geometry_status=unavailable`; no hay coordenadas inventadas ni geocodificación. Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

Se excluyen formularios «Solicitud licencia de obras», «Solicitud licencia segregación y/o agrupación», tasas por licencias, ordenanzas generales y el perfil del contratante. No son licencias concedidas ni proyectos físicos individuales.

## Validación reproducible

Runtime preinstalado, sin instalar dependencias:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sonseca -v
```

Cinco pruebas correctas: estructura de tarjetas y exclusiones; agrupación documental e identificador estable; rechazo de respuestas vacías, URLs ajenas y paginación; extracción y actualización con validación del PDF; manifest y licencias desactivadas.

Se ejecutó realmente `SonsecaAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`. Se volvió a analizar la captura HTML y se comprobó el recuento contra el JSONL. Evidencia local sin incorporar a fuentes: `evidence/proyectos.jsonl`, `evidence/validation.json` (live_records=1, URLs, hora UTC y limitaciones), `evidence/documentos.html`, PDF nombrado por SHA-256, PDF descriptivo de investigación y `evidence/normas-portada.png`. No se ejecutaron bases de datos, publicación ni pasos del pipeline externo.
