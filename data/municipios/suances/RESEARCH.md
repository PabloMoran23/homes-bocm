# Suances — INE 39085, Cantabria

Verificación: 2026-11-08. Adaptador único `SuancesAyuntamientoAdapter`.
Cobertura parcial de dos inventarios municipales completos, consultados en vivo
por el adaptador. Ocho registros reales, sin coordenadas ni fechas inferidas.
`publication_ready=false`; programación, licencias y jitter desactivados.

## Fuentes oficiales descubiertas

- https://suances.es/ayuntamiento/plan-general-de-ordenacion-urbana/
  — HTTP 200. Tres secciones explícitas: «PGOU - VIGENTE», «Avance aprobación
  inicial nuevo PGOU (no vigente)» e «Informe sostenibilidad». Se extraen dos
  instrumentos, no un proyecto por plano o anejo. El informe de sostenibilidad y
  los anexos de ordenación detallada se conservan dentro del expediente del nuevo
  PGOU. Su título de sección no acredita una fecha de acuerdo ni la vigencia.
- https://suances.es/ayuntamiento/proyectos-en-curso/
  — HTTP 200. Inventario específico con seis fichas de obras físicas y
  descripciones sustantivas: rehabilitación del Palacio de Jaime del Amo,
  reurbanización de calle Piélagos, Bulevard Viares y parque infantil, nueva
  oficina de turismo, segunda fase del Paseo Marítimo y renovación del campo de
  fútbol. Se conservan descripciones e imágenes enlazadas, con procedencia de la
  página municipal. No son anuncios de contratación ni noticias generales.
  **El texto conserva previsiones para 2023 y la temporada 2022/23**: su presencia
  actual en la web no demuestra que las obras continúen en ejecución. No se
  asigna fase actual; `estado_actual_verificado=false`.
- https://transparencia.aytosuances.com/economica/planes-urbanisticos-y-estudios-de-impacto-ambiental/
  — HTTP 200. Portal municipal enlazado desde la web principal; remite al archivo
  regional de planeamiento de Suances, corroborando la procedencia oficial.
- https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/suances
  — HTTP 200. Archivo del Gobierno de Cantabria, enlazado también como
  «Documentación completa» del PGOU vigente. Se conserva ese enlace como
  `registro_planeamiento`, sin afirmar que se hayan enumerado todos sus
  expedientes ni extraído geometrías. La respuesta capturada muestra navegación
  municipal; no se usa como inventario adicional de registros en este adaptador.
- https://suances.es/ayuntamiento/exposicion-publica-de-documentos/
  — HTTP 200. Tablón mixto con ordenanzas, procedimientos, modificaciones de
  planeamiento y estudios de detalle. Se identificaron referencias a la
  modificación puntual 22 (2025-501), San Martín (2025-507), San Juan (2025-151)
  y Atajo (2025-636). **Queda fuera de esta cobertura**: requeriría agrupar cada
  expediente y leer sus documentos para establecer su secuencia y fechas.
  No se confunde la información pública con una licencia concedida.

Las primeras peticiones sin User-Agent recibieron una desconexión. Las consultas
posteriores con User-Agent de navegador y la ejecución real del adaptador
obtuvieron HTTP 200 sin autenticación.

## Modelo, procedencia y límites

Los dos inventarios extraídos son páginas estáticas sin paginación observada.
Todos los cuerpos de acordeón están presentes en el HTML: se recorren completos,
incluidos los inicialmente colapsados. No hay límite de fichas ni documentos.
Si aparece paginación, el parser falla explícitamente y exige revisar el recorrido;
no acepta silenciosamente la primera página. También falla ante cambios en las
secciones de planeamiento, fichas incompletas o fuentes documentales inesperadas.

El PGOU vigente tiene un enlace regional; el nuevo no vigente tiene 148 enlaces
únicos agrupados. Entre ellos se retiene la «Instancia» como
`formulario_alegaciones`, nunca como registro de proyecto o licencia. Planos,
memorias, normativa, informes y anexos mantienen título, URL, sección y
`provenance_url`. La fuente municipal enlaza documentos alojados en
`suancesurbanismo.atys.net`; ese alojamiento no se presenta como una fuente
independiente. Los enlaces se conservan tal como están publicados; no se verificó
exhaustivamente la disponibilidad ni el contenido de cada PDF. Las obras tienen
15 enlaces de imágenes en total, etiquetados como imágenes, sin confundirlos con
resoluciones o proyectos técnicos.

Los identificadores se derivan de la URL del inventario y del instrumento o del
título normalizado de la obra; no dependen de los identificadores aleatorios de
los acordeones. No se inventan números de expediente. Una modificación del
título de una obra puede cambiar su identidad. La actualización vuelve a
extraer la instantánea completa de ambas páginas, no promete un histórico ni
una detección incremental de bajas.

`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan separadas y nulas:
ni los directorios de subida ni las previsiones de obra son fechas de aprobación.
`lat`, `lon` y `geometry` son nulos; no se usan centroides municipales ni jitter.
No se ha verificado un registro de licencias concedidas. Los formularios y los
procedimientos no se convierten en licencias.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_suances -v`: seis pruebas correctas. Comprueban
  agrupación y vigencia, fechas y geometría nulas, procedencia, rechazo de
  navegación o secciones cambiadas, rechazo de paginación, exclusión de
  formularios/licitaciones, duplicados, escritura del snapshot y manifest.
- Ejecución real:
  `SuancesAyuntamientoAdapter(config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
  Resultado: `count=8`, `written=8`, `status=ok`.
- `evidence/validation.json`: `live_records=8`, URLs, limitaciones, fecha UTC,
  cantidades documentales y pruebas realizadas.
- `evidence/pgou.html` y `evidence/proyectos.html`: respuestas obtenidas por el
  adaptador durante la extracción. Capturas adicionales: `exposicion.html`,
  `aucan.html`, `source-104622.html` (transparencia) y `source-180144.html`
  (consulta inicial de la página del PGOU).

La evidencia es local y no forma parte de los cuatro archivos fuente solicitados.
No se modifican adaptadores compartidos ni dependencias.
