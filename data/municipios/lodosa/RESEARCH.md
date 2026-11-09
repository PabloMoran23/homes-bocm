# Lodosa — Navarra — INE 31157

Verificación en vivo: 2026-11-09. Adaptador único:
`municipio.adapters.lodosa:LodosaAyuntamientoAdapter`.

## Descubrimiento y alcance

La portada oficial https://www.lodosa.es/ enlaza «Ayudas Europeas» a
https://www.lodosa.es/ayuntamiento/ayudas-europeas/ . Esta página es un
inventario municipal actual accesible por HTTP 200, con tres secciones explícitas
«PROYECTO n», beneficiario Ayuntamiento de Lodosa y tablas de identificación.
Se recorre toda la página, sin filtro temporal ni límite de registros. No se
observó paginación; si aparecen enlaces de paginación, el adaptador falla antes
de sustituir la salida. Las actualizaciones vuelven a leer el inventario completo.
No constituye un censo de todas las obras, licencias o instrumentos de planeamiento.

Inventarios adicionales investigados:

- https://lodosa.sedelectronica.es/transparency : enlazado desde la portada;
  categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con cuatro elementos,
  navegación dinámica Wicket no incorporada a la cobertura. No se afirma haber
  extraído esos cuatro elementos.
- https://lodosa.sedelectronica.es/info.0 : contiene solicitudes de licencia,
  que no acreditan concesiones. Licencias deshabilitadas y salida vacía explícita.
- https://www.lodosa.es/lodosa-echa-raices/ : estrategia participativa y diagnóstico
  del casco histórico; no se interpreta como aprobación de un plan ni de una
  rehabilitación. Fuera de este inventario.

## Registros reales y documentos agrupados

1. Restauración medioambiental en el entorno de la Torre de Velasco. Dos documentos
   bajo el mismo proyecto: convenio TEDER y adenda. La tabla identifica la acción
   local 3.1.2; el CRU está pendiente en la fuente. La página indica 57.095,98 euros.
   El convenio descargado describe expresamente la ejecución de esta actuación.
2. Actuación singular local de energía limpia en el colegio público Ángel Martínez
   Baigorri. Expediente original `PR-D5000-2021-002573`, CRU `IND020351` en
   `identificacion_fuente`. Un PDF de comunicación de certificación final. Su texto
   acredita una ampliación fotovoltaica ejecutada de 91 módulos y 49,14 kWp.
   Estos detalles del PDF se usan para verificar la naturaleza física del proyecto;
   el parser extrae la identificación de la página, sin interpretar automáticamente
   los PDFs. La página deja vacía la inversión total; no se rellena desde el PDF.
3. Reformas y mejoras de audio, iluminación y vídeo digital del auditorio de la Casa
   de Cultura. CRU `IND 001355`. Registro respaldado por título, beneficiario y tabla
   municipales; no hay documento específico enlazado en esta sección. No se deduce
   finalización ni adjudicación de la financiación indicada.

Los documentos se conservan en `documentos`, con título, URL y página de procedencia.
Se excluyen planes antifraude, enlaces institucionales genéricos, portales de
monitorización, formularios y noticias ajenas. Los IDs dependen del título normalizado,
no del número de posición. Un cambio de denominación puede generar otro ID; no se
promete reconciliación histórica. No hay deduplicación entre inventarios externos.

## Semántica y límites

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos:
no hay fechas explícitas de esos hechos en las fichas de inventario. La fecha del
nombre o directorio de un PDF no acredita publicación ni aprobación. La adenda tiene
etiqueta municipal «19/11/2025», pero el texto del documento dice «12 de noviembre
de 2025» y cita el convenio de 10 de marzo de 2025. Son contextos documentales,
no fechas de aprobación del proyecto; se mantiene la etiqueta original en el enlace.
Los códigos PRTR se conservan literalmente, incluso aparentes incoherencias de la
fuente. Los importes son texto financiero original, no adjudicaciones ni pagos.

La salida no contiene descripción general sin filtrar de la página; sólo título,
identificación pública, beneficiario, importes y enlaces documentales del proyecto.
Las capturas HTML son selectivas con ese mismo alcance y omiten widgets ajenos.

`geometry_status: unavailable`: ni las fichas ni las tablas proporcionan geometría
verificada por proyecto. No se utiliza el centroide municipal ni coordenadas
inventadas. `publication_ready=false`, `geocode.jitter_missing=false`,
`schedule.enabled=false`. La anotación compartida de entidades clasifica estos
registros como desconocidos; no se fuerza su elegibilidad ni publicación.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_lodosa -v`: tres pruebas pasan. Comprueban
agrupación y deduplicación documental, fechas nulas, estabilidad del ID al renumerar,
exclusión de texto ajeno, rechazo de paginación y estructura incompleta, carga del
manifest, licencias deshabilitadas y conservación de salida anterior ante fallo.

Extracción real mediante `load_portal_adapter(load_manifest('lodosa')).backfill_proyectos`
a `evidence/proyectos.jsonl`: **3 registros**, **3 PDF** descargados, HTTP 200 y
cabecera `%PDF` comprobada. Los primeros textos de los PDF se revisaron con
`pdftotext` preinstalado. La captura selectiva vuelve a producir los mismos tres IDs.
`evidence/validation.json` documenta URLs, fecha de comprobación, hashes, capturas,
conteo y limitaciones. La evidencia es local y no forma parte de los cuatro archivos
fuente. No se ha publicado ni accedido a servicios de despliegue o bases de datos.
