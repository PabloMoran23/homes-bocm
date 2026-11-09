# Olvera — INE 11024, Cádiz, Andalucía

Investigación y extracción real: 8 de noviembre de 2026.

## Fuentes descubiertas y selección

Fuente primaria: [Instrumentos Urbanísticos del Ayuntamiento de Olvera](https://www.olvera.es/es/normativa-legal/instrumentos-urbanisticos). Es un registro municipal público con tabla de inscripción, notas marginales, cancelaciones/rectificaciones y enlaces a memorias, planos y boletines. La página viva devuelve HTTP 200 y contiene 24 inscripciones numeradas consecutivamente, sin paginación observada. Se procesa toda la tabla, sin límite de registros. Si aparecen controles de paginación se aborta explícitamente para revisar cobertura; no se devuelve una primera página como inventario completo. También se rechazan estructura ausente, filas inesperadas, números repetidos o saltos de numeración.

Se localizaron también [Urbanismo](https://www.olvera.es/es/servicios-municipales/urbanismo), que es un directorio de personal, y la [sede electrónica](https://olvera.sedelectronica.es/info.0), que ofrece trámites como solicitudes de licencia. No son un registro de concesiones y no se extraen. La búsqueda descubrió asimismo documentación del nuevo Plan Básico de Ordenación Municipal en nuevoplandeolvera.es; ese portal y sus fases no forman parte del alcance de este adaptador. No se afirma exhaustividad del planeamiento municipal, actualidad jurídica de los instrumentos ni cobertura de todas las obras públicas.

## Unidad de registro y procedencia

Resultado vivo: **21 instrumentos**, con **87 URLs documentales únicas dentro de cada instrumento**. Son 20 inscripciones no canceladas más la adaptación parcial incluida documentalmente en la inscripción 1. Entre ellas: NN.SS. de 1999, modificaciones UE-9/UE-10/UE-4, planes parciales SAU-1 Oeste y SAU-2 Centro, Recinto Ferial, desclasificación SAU-5 y estudios de detalle Calle Pruna y Avda. Diputación.

Las inscripciones 2, 9, 10 y 11 se excluyen por su anotación expresa de cancelación; la evidencia de validación conserva número y motivo. En las tres últimas el propio registro declara que no existe planeamiento de desarrollo aprobado. Las inscripciones 4 y 7 sí identifican instrumentos y aprobación, aunque no tienen PDF adjunto: se conserva la ficha del registro como fuente y una lista documental vacía.

Cada inscripción agrupa todos sus documentos, conservando URL absoluta, títulos y página de procedencia. Los duplicados del mismo PDF dentro del grupo reúnen sus títulos sin multiplicar instrumentos. La inscripción 1 contiene dos instrumentos distinguibles: NN.SS. de 1999 y «1ª Adaptación Parcial NN.SS.». Se separan mediante el directorio documental explícito `NNSS_adaptacion_parcial-1`, con relación al registro base. No se heredan las fechas de 1999 a la adaptación.

Los identificadores locales proceden del número oficial de inscripción. `expediente_grupo` expresa literalmente «Registro de instrumentos urbanísticos, inscripción N»: es una referencia de agrupación documental, **no un número de expediente administrativo inventado**. `source_locator` identifica fila y, en la adaptación, apartado. `clase_planeamiento_fuente` conserva los códigos de la inscripción. Un código PG sin figura suficiente se presenta como instrumento de planeamiento, sin inventar una modificación concreta.

## Fechas, vigencia y límites

`fecha_aprob` se transcribe exclusivamente del campo «5º.- APROBACIÓN DEFINITIVA»; `fecha_publicacion` exclusivamente de la columna de BOP/BOJA, con `fecha_publicacion_tipo: boletin_oficial_segun_registro`. No son fechas de publicación web. Para la adaptación, `fecha_acuerdo: 2010-05-18` procede de la anotación que cita expresamente el acuerdo plenario. Las fechas de anotación/rectificación no se convierten en aprobaciones. Se conservan textos originales de aprobación, referencia de boletín y notas. Las fechas ausentes o ambiguas se omiten. El registro usa años de dos cifras; se interpretan 90–99 como 1990–1999 y 00–89 como 2000–2089, exclusivamente para este registro histórico.

Las fechas no se han contrastado exhaustivamente con los boletines. Hay aparentes inconsistencias originales: por ejemplo, inscripción 14 indica aprobación 11/11/07 y BOJA 11/10/07; se transcriben ambas sin corregirlas por conjetura. Se conserva igualmente el número de boletín que declara la fuente, aunque pudiera contener errores. Las notas de rectificación siguen asociadas a cada instrumento. La presencia en la web no certifica vigencia actual: `vigencia_verificada: false`.

No se extrae el contenido completo de todos los PDF ni se verifica su disponibilidad exhaustiva. No hay geometría, coordenadas, geocodificación, fases deducidas ni licencias concedidas. `publication_ready: false`, `geometry_status: unavailable`. Manifest: `licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`. La actualización vuelve a consultar el inventario completo; no utiliza marcas temporales que puedan ocultar documentos históricos.

## Validación reproducible y evidencia local

Runtime requerido: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `-m unittest municipio.test_olvera -v` — **5 correctos**. Cubren agrupación/deduplicación, aislamiento entre instrumentos, separación de adaptación y fechas, cancelaciones, estructura inválida, paginación, fechas inválidas, carga por manifest y métodos de extracción/actualización y licencias desactivadas.

Extracción real realizada mediante `load_manifest('olvera')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, añadiendo únicamente `manifest.portal.config['evidence_dir']='evidence'` para capturar la respuesta. El clasificador compartido se ejecuta por el registro de adaptadores: 21 registros, cero entidades pendientes, estado `ok`.

Evidencia sin publicar ni incorporar al código: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/instrumentos.html` y el informe derivado `evidence/proyectos.entities.json`. La validación incluye `live_records`, `source_urls`, límites, timestamp UTC, SHA-256 de captura y resultados de pruebas. Se descargaron dos muestras oficiales: Calle Pruna (1.701.974 bytes) y primer tomo de UE-6 (10.998.466 bytes), ambas HTTP 200, `application/pdf`, firma `%PDF-`; capturas `evidence/olvera-registro-18.pdf` y `evidence/olvera-registro-22.pdf`. Esto comprueba disponibilidad de esas dos muestras, no de todos los enlaces.

Sin cambios compartidos, dependencias nuevas, base de datos, publicación ni despliegue.
