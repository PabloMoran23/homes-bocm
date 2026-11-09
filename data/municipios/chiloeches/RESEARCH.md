# Chiloeches — Guadalajara — INE 19105

Verificación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente oficial

La web del Ayuntamiento https://chiloeches.es/ enlaza, en Ayuntamiento →
Transparencia → Urbanismo, el inventario https://chiloeches.es/urbanismo/.
La página respondió HTTP 200 y contiene un bloque POM con documentos, tres
modificaciones puntuales y dos secciones de planos. Se extrae el inventario
actual completo de ese bloque, sin semillas de noticias individuales, filtros
cronológicos ni límite de filas. No presenta paginación. El parser rechaza enlaces
de paginación, cambios de encabezado y grupos sin documentos para evitar aceptar
una extracción silenciosamente incompleta.

Resultado real: **4 instrumentos y 72 enlaces PDF únicos**:

- POM de Chiloeches: 43 documentos (memoria y planos de información/ordenación).
- Modificación puntual nº 4: 20 documentos.
- Modificación puntual nº 5: 7 documentos; dos rótulos municipales de la misma
  memoria enlazan el mismo PDF, conservados como alias de un único documento.
- Modificación puntual nº 6: 2 documentos.

Los planos de información y ordenación pertenecen al POM y no generan proyectos
independientes. Se conserva la sección exacta del índice, su URL y el enlace
original de cada documento. Algunas versiones de planos del POM mencionan MP6:
se mantiene su ubicación en el índice, sin inventar instrumentos adicionales.
El documento NORMAS URBANISTICAS está bajo MP5 en el índice y se conserva ahí;
esta asociación describe la organización municipal, no acredita autoría o fecha.
Los IDs derivan del instrumento (POM/número de modificación), no de cada PDF.

## Comprobaciones documentales y semántica

Se comprobaron los 72 enlaces mediante HEAD: todos HTTP 200 y application/pdf.
Se descargó un PDF representativo por instrumento, verificando cabecera PDF y
registrando URL, tamaño y SHA-256 en `evidence/*.source.json`.

`MEMORIA.pdf` contiene un documento refundido de normas urbanísticas del POM,
con portada «Noviembre de 2009», aunque el índice lo rotula MEMORIA. La memoria
de MP5 lleva «Julio de 2011» y el texto de MP6 identifica expresamente esa
modificación. El PDF principal de MP4 es escaneado y `pdftotext` no devuelve texto
legible: su identificación procede del grupo y rótulo del índice municipal.
No se ha realizado OCR ni una auditoría jurídica de cada documento.

Las fechas de portada son fechas documentales, **no fechas de acuerdo**. La página
no ofrece fechas de publicación o acuerdo de los instrumentos, ni una fase
acreditada. `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase`
quedan nulos. El nombre `TEXTO FINAL_APROBADO.pdf` no se convierte en una
aprobación definitiva ni se toma la fecha técnica de WordPress como publicación.
El índice disponible hoy no demuestra por sí solo la vigencia jurídica de cada
versión histórica.

## Cobertura parcial y exclusiones

Se cubre únicamente el catálogo documental municipal de POM. No se declara un
registro exhaustivo de expedientes, obras o licencias de Chiloeches. No se
extraen formularios de https://chiloeches.es/solicitudes/, ordenanzas fiscales,
licitaciones ni noticias como concesiones o proyectos. Licencias deshabilitadas:
no se ha verificado un inventario de concesiones.

La búsqueda también localizó el registro regional de PAU:
https://urbanismo.castillalamancha.es/registros/pau/pau-de-los-sectores-1-y-2-de-chiloeches
No se integra en este adaptador: sería otra cobertura y requiere auditar su propio
inventario, estados y discrepancias de fechas. No se confunde con una concesión
municipal de licencia.

Geometría: `geometry_status: unavailable`. Hay planos PDF enlazados, pero no se
ha verificado un servicio vectorial ni geometrías por instrumento. No se
vectorizan planos ni se asigna el centro municipal como coordenada del proyecto.
`lat`, `lon` y `geometry` nulos, `publication_ready: false`;
`geocode.jitter_missing: false`, `schedule.enabled: false`.

## Validación reproducible

`python -m unittest municipio.test_chiloeches -v`: 6 pruebas correctas.
Cubren agrupación, deduplicación, procedencia, fechas nulas, IDs estables,
paginación, cambios de estructura, documentos ajenos, exclusión de formularios,
actualización de instantánea y licencias deshabilitadas.

La extracción se ejecutó realmente mediante
`ChiloechesAyuntamientoAdapter('chiloeches', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Captura HTML, JSONL de cuatro registros, PDFs representativos, textos extraídos,
comprobaciones de enlaces y resumen en `evidence/validation.json`. Evidencia local,
excluida del control de versiones. No se ejecutan pipeline completo, publicación,
base de datos, despliegue ni sincronización.
