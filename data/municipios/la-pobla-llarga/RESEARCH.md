# la Pobla Llarga — INE 46203, Valencia

Investigación y extracción real: 9 de noviembre de 2026. Se revisaron primero
`municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de adaptadores
y los ejemplos Chipiona y Hernani. No se modifica código compartido.

## Fuente oficial y descubrimiento

- Portal municipal: https://lapoblallarga.sedelectronica.es/transparency
- Sección 7, Urbanismo, obras públicas y medio ambiente:
  https://lapoblallarga.sedelectronica.es/transparency/16be556a-228b-4564-ad83-3d068b3dd182/
- Sección 7.1, Planeamiento urbanístico (fuente del adaptador):
  https://lapoblallarga.sedelectronica.es/transparency/73d2c18c-54c7-431e-8b72-ec18e1e40b5c/

El portal raíz publica 11 documentos en la sección 7.1. En la sección 7 las
carpetas 7.2 medio ambiente, 7.3 normativa, 7.4 obras públicas y 7.5 indicadores
indicaban cero documentos. El portal raíz también muestra una sección distinta
«9. PLANS MUNICIPALS» con 58 documentos, fuera de la cobertura implementada.
La web principal https://www.lapoblallarga.es no respondió a la conexión y el
antiguo dominio .net no resolvió. Esto no impidió acceder a la sede municipal.
La sede ofrece solicitudes de licencia; no constituyen concesiones y no se
extraen. No se usan resultados de buscadores, contratación ni noticias como
registros de proyectos.

Se comprobó además el inventario autonómico SIGIF:
https://prevencionincendiosgva.es/Planificacion/DetallePlanesMunicipio/479
Identifica explícitamente Pobla Llarga (la), 46203, Valencia, y enlaza PLPIF,
LOTUP y plan de quemas. Se conserva como descubrimiento auxiliar; no se mezcla
con el instrumento urbanístico municipal ni se extraen planes comarcales como
proyectos locales.

## Unidad extraída y documentos

**Un registro real: Plan General de Ordenación Urbana (PGOU) de la Pobla Llarga.**
La denominación se sustenta en «NORMAS PGOU» y «RESOLUCIÓN APROBACION DEFINITIVA
PGOU» del inventario; el PDF de normas corresponde al planeamiento municipal.
No se crea una actuación sintética a partir de una página genérica.
Los once documentos se agrupan como partes del mismo instrumento:

- Cinco en la carpeta principal: Corrección errores BOP, NORMAS PGOU,
  01_planos, RESOLUCIÓN APROBACION DEFINITIVA PGOU y Memoria justificativa.
- Tres en «1. APROBACIÓN»: ACUERDO, RESOLUCIÓN y CORRECCION ERRORES BOP.
- Uno en «2. MEMORIA JUSTIFICATIVA»: MEMORIA.
- Uno en «3. NORMAS URBANISTICAS»: NORMAS PGOU.
- Uno en «4. PLANOS»: PLANOS.

Cada documento mantiene título literal, enlace estable `preview-document/UUID`,
URL de inventario de origen y sección cuando procede. No se eliminan documentos
con UUID distinto porque podrían ser versiones diferentes o duplicados de
contenido. Tampoco se convierten en proyectos independientes. No se almacenan
los enlaces temporales del visor PDF como identificadores.

Las carpetas se recorren mediante callbacks Wicket obtenidos en una sesión
pública nueva; el servidor redirige a URLs estables de carpeta sin autenticación.
Se renueva la página principal antes de cada navegación. Se comprueba el número
de documentos anunciado en cada subcarpeta (3+1+1+1) y los cinco documentos de la
raíz. No hay paginación visible en estas cinco carpetas. El adaptador rechaza
paginación, cambios de estructura no revisados, IDs repetidos entre carpetas,
subcarpetas adicionales o recuentos incompletos, antes de reemplazar la salida.
Esto delimita la cobertura sin truncar silenciosamente.

## Fechas, estado y límites

Cobertura parcial del inventario documental actual del PGOU, sin historial
completo municipal, modificaciones posteriores, obras públicas ni licencias.
El título del documento de resolución no demuestra por sí solo vigencia actual.
No se asignan fase, fecha de publicación, fecha de acuerdo o fecha de aprobación.
La fecha de creación del CMS observada en el visor no se convierte en ninguna
de esas fechas. La resolución es un PDF escaneado: `pdftotext` no produjo texto
utilizable, por lo que no se interpreta su fecha mediante suposiciones.

No hay coordenadas ni geometría verificadas: `geometry_status: unavailable` y
`publication_ready: false`. El manifiesto desactiva licencias, programación y
jitter. La política compartida añade `pendiente/insufficient_identity_evidence`
al registro por carecer de referencia numérica de expediente; no se inventa una
para cambiar esa clasificación. El registro conserva su identidad documental
del PGOU y permanece sin preparación para publicación.

## Verificación reproducible

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`

Pruebas: `-m unittest municipio.test_la_pobla_llarga -v`: **7 correctas**.
Cubren agrupación, recorrido de todas las secciones, procedencia, ausencia de
fechas/coordenadas inferidas, fuentes externas, paginación, cambios de estructura,
recuentos incompletos y conservación de salida anterior ante fallo.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local.
Resultado: **1 registro, 11 enlaces documentales**. Se descargaron adicionalmente
los PDF de normas (20.867.452 bytes) y resolución (522.379 bytes): HTTP 200,
`application/pdf`, firma `%PDF-` válida. Las capturas y hashes permiten revisar
la procedencia, sin afirmar haber interpretado todos los planos o documentos.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, resultado de pruebas, capturas HTML de las cinco
carpetas, visores documentales y ambos PDF. La validación enumera todas las URLs
extraídas, recuentos, limitaciones y clasificación compartida. No se ejecutan
publicación, base de datos, geocodificación ni scripts de despliegue.
