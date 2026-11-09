# Arévalo — Ávila — INE 05016

Investigación y extracción real: 8 de noviembre de 2026. Adaptador único:
`municipio.adapters.arevalo:ArevaloAyuntamientoAdapter`.

## Fuentes oficiales descubiertas

1. [Urbanismo municipal](https://arevalo.es/servicios-municipales/urbanismo/):
   identifica el ayuntamiento (Plaza del Real 12, Arévalo, Ávila), enlaza Normativa
   tramitación, información del polígono industrial y el archivo PLAU de la Junta.
   El enlace autonómico usa provincia `05`, municipio `016`; PLAU confirma
   expresamente `ARÉVALO Código INE: 05016`. No confundir con Nava de Arévalo,
   Montejo de Arévalo o Arévalo de la Sierra.
2. [Normativa tramitación](https://arevalo.es/servicios-municipales/urbanismo/normativa-tramitacion/):
   **fuente extraída**. Inventario vivo de documentos, con pestañas cuyo contenido
   completo está en el HTML inicial, incluso la pestaña no activa. Dos instrumentos
   reales del planeamiento de Arévalo: modificación puntual 28 (documentación de
   aprobación provisional) y modificación puntual 27 (documentación de aprobación
   inicial). Hay tres PDF; textos y planos de la 27 se agrupan en un instrumento.
   No se produce un registro por enlace de ver/descargar ni por documento.
3. [Archivo PLAU para Arévalo](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion&pager.sortindex=-3&provincia=05&municipio=016):
   inventario autonómico enlazado por el ayuntamiento. Consulta exploratoria de
   **las tres páginas completas** (offsets 0, 15 y 30; 15 + 15 + 14 = 44 entradas).
   No forma parte de la extracción de este adaptador. Incluye PGOU, modificaciones,
   planes parciales, estudios de detalle y proyectos de actuación/urbanización.
   La primera página publica la modificación 28 el 23/09/2026, con acuerdo
   29/01/2026, y la 27 el 25/06/2026, con acuerdo 29/05/2026. Esos pares son
   columnas distintas del archivo, no fechas verificadas para los PDF del
   inventario municipal. No se transfieren a los registros extraídos.
4. [Solicitudes e instancias](https://arevalo.es/solicitudes-e-instancias/):
   el resultado de descubrimiento enumera modelos de solicitud de obra mayor,
   declaraciones responsables y otros trámites. No es un registro de licencias
   concedidas. Licencias desactivadas. Tampoco se extraen noticias o anuncios
   de contratación como si fueran proyectos o autorizaciones.

## Documentos y procedencia

- Modificación 28: [PDF municipal](https://arevalo.es/wp-content/uploads/2026/02/MP-28-DEL-PGOU-AREVALO-APROBACION-PROVISIONAL.pdf).
- Modificación 27: [textos](https://arevalo.es/wp-content/uploads/2026/02/TEXTOS_MODIFICACION-PUNTUAL-27-AREVALO_compressed.pdf)
  y [planos](https://arevalo.es/wp-content/uploads/2026/02/PLANOS_MODIFICACION-PUNTUAL-27-AREVALO_compressed.pdf).

Los tres fueron descargados con HTTP 200, Content-Type application/pdf y firma
`%PDF-`. Se conservan íntegros en evidencia local; la extracción obtiene títulos y
agrupación del HTML, no interpreta el contenido de los PDF. Cada documento conserva
su título literal, URL y página de procedencia. La URL del primer PDF es una
conveniencia; `documentos` retiene todos los enlaces del instrumento.

## Cobertura y semántica

Cobertura **parcial**, exclusivamente el inventario documental municipal de
Normativa tramitación servido actualmente. No es un histórico completo ni una
lista exhaustiva del planeamiento vigente, obras ejecutadas o licencias otorgadas.
PLAU contiene publicaciones posteriores para las modificaciones 27 y 28: la fase
del PDF municipal no determina la fase actual del expediente. Por ello se conserva
`fase_documental`, se omite la fase canónica y se declara
`estado_actual_verificado: false`. El título mantiene la etiqueta documental.
Las 44 entradas autonómicas se investigaron, pero no se presentan como extraídas.

`fecha_publicacion` y `fecha_acuerdo` son nulas. El directorio `/2026/02/` es una
ruta de subida, no una fecha de publicación ni de aprobación. No se han deducido
fechas de las versiones municipales ni atribuido las fechas autonómicas a ellas.
No hay coordenadas ni geometría inferidas; `publication_ready: false` y
`geometry_status: unavailable`. `schedule.enabled`, `geocode.jitter_missing` y
`licencias.enabled` son false.

No hay paginación en el inventario municipal observado. Se procesan todas las
pestañas, no solo la activa. Si aparecen controles de paginación reconocibles,
el adaptador falla expresamente para evitar truncar. También falla ante cambio
de página, ausencia de paneles/documentos, documentos ajenos al número de
instrumento, duplicidad ambigua de instrumentos o URLs inesperadas. Las
actualizaciones regeneran la instantánea completa; no aplican una fecha de corte.

## Verificación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_arevalo -v` con ese runtime:
**5 pruebas correctas**. Cubren agrupación de documentos, aislamiento entre
instrumentos, exclusión de formularios, fases documentales y fechas nulas,
cambios de estructura/paginación, URLs ajenas, IDs estables, manifiesto,
actualización de instantánea y licencias desactivadas. Los fixtures son HTML
mínimo independiente de la red; no requieren evidencias externas para funcionar.

Extracción real mediante `load_manifest('arevalo')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **2 registros y 3 enlaces documentales**. Se ejercitó también la
anotación compartida de política de entidades del registro de adaptadores.

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: resultado real del adaptador.
- `evidence/validation.json`: cantidad, fuentes, limitaciones y validación.
- `evidence/inventory-live.html`: respuesta de la ejecución real.
- `evidence/urbanismo.html`, `tramitacion.html`: capturas de descubrimiento.
- `evidence/documento-1.pdf` a `documento-3.pdf`: documentos municipales.
- `evidence/plau.html`, `plau-15.html`, `plau-30.html`: tres páginas autonómicas.
- `evidence/plau-discovery.json`: títulos y recuentos de las tres páginas.
- `evidence/source_checks.json`: URLs, códigos HTTP, tamaños y firmas PDF.
- `evidence/parser-tests.txt`: salida de las pruebas.

Sin dependencias nuevas, cambios compartidos, acceso a bases de datos ni publicación.
