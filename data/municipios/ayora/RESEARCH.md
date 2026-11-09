# Ayora — INE 46044, Valencia

Comprobación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales e inventario actual

La sede electrónica municipal se identifica como «Sede Electrónica de Ayora» y
ofrece públicamente, sin identificación, el [portal de transparencia](https://ayora.sedelectronica.es/transparency).
El apartado [7. Urbanismo, obras públicas y medio ambiente](https://ayora.sedelectronica.es/transparency/e73dc69f-1b97-454a-b35a-efa01a5658ef/)
publica distintas colecciones. Se descubrieron mediante los callbacks públicos
Wicket y su cabecera `Ajax-Location`; no se ejecuta JavaScript remoto.

La fuente implementada es el [inventario 7.1 Planeamiento urbanístico](https://ayora.sedelectronica.es/transparency/88db6e49-debd-458a-8554-540c216cc18b/).
En la comprobación contiene 20 documentos: uno suelto denominado «DOCUMENTO
ACTUACION PREVIA» y una carpeta de instrumento con 19 documentos.
La [modificación puntual del Plan Parcial Calderones asumido por PGOU](https://ayora.sedelectronica.es/transparency/ed4eb4c4-dc6b-4d93-88de-7075a35a92b3/)
es un instrumento real, con borrador, documento inicial estratégico, planos de
situación, ordenación actual y propuesta, informes, consultas, certificados y
decretos. Se extrae **un registro con 19 documentos**, no 19 actuaciones distintas.
Los títulos y los enlaces `preview-document` proceden del inventario actual.
Cada documento conserva su carpeta de procedencia y, cuando existe, su atributo
`title` como `descripcion_fuente`.

Se abrió también la [ficha del borrador](https://ayora.sedelectronica.es/preview-document/e558f989-15eb-4ecd-a865-0fb268c44016):
HTTP 200, documento electrónico en formato PDF, con nombre coincidente y datos
de integridad. Se capturó esa ficha HTML; no se descargó ni analizó el PDF.
Su fecha de creación en la sede no se interpreta como publicación o acuerdo.

## Cobertura y semántica

Cobertura deliberadamente parcial: solo carpetas de instrumentos en 7.1.
El documento suelto queda excluido por no identificar inequívocamente un
instrumento propio. No se transforma la página genérica en un proyecto.
Se exploró también [7.9 Proyectos en exposición pública](https://ayora.sedelectronica.es/transparency/b3d6e692-2ed9-49a6-853e-aa79a850da4e/),
que incluye explotaciones porcinas, proyectos fotovoltaicos y varias exposiciones
del mismo plan especial supramunicipal. Ese apartado no está implementado ni se
atribuye cobertura de sus documentos. Tampoco se extraen 7.2, 7.6, PUAM,
planes de emergencia u otros apartados. La categoría 7.4 Obras públicas mostraba
cero documentos en la primera página del inventario superior observado.
La web `https://www.ayora.es` cerró la conexión durante la investigación; la
extracción no depende de ella. No se usa la información de fuentes de terceros.

Sin fechas de aprobación, acuerdo o publicación inferidas; esos campos son nulos.
Ni «Certificado acuerdo Pleno» ni los años en los nombres acreditan por sí solos
la fecha o el contenido de un acuerdo. Los intervalos de publicación de algunos
certificados se conservan literalmente en sus títulos, sin asignarlos a todo el
instrumento. No se afirma vigencia, aprobación definitiva, ejecución de obras ni
licencia concedida. No se extraen coordenadas, parcelas geométricas ni centroides.
Todos los registros tienen `publication_ready: false` y geometría no disponible.
Licencias, programación y jitter están desactivados en el manifest.

## Navegación y comprobaciones

El adaptador obtiene de nuevo el inventario y resuelve las carpetas desde sus
callbacks de sesión. No contiene registros precargados ni enlaces temporales
fijos de descarga. Sigue todos los botones «Mostrar más» de cada listado visitado;
para Calderones se observaron 10 documentos iniciales y 9 adicionales en una
respuesta XML de Wicket. Agrupa subcarpetas dentro de su instrumento si aparecen.
Contrasta el total de documentos únicos con la cifra publicada en cada carpeta.
Una discrepancia, respuesta desconocida, bucle, falta de progreso o superación
del límite de seguridad de paginación aborta sin escribir una salida parcial.
No se interpreta la primera página de categorías como todo el portal.

`python -m unittest municipio.test_ayora -v`: **10 pruebas correctas**, incluyendo
agrupación, semántica sin fechas inventadas, aislamiento y deduplicación de enlaces,
paginación XML, detección de bucles, discrepancias de recuento y manifest.
Se ejecutó además `AyoraAyuntamientoAdapter.backfill_proyectos` contra la sede real:
**1 registro, 19 documentos, 1 documento suelto excluido**.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live-captures/` (peticiones de la extracción
y respuestas HTML/XML), y capturas de descubrimiento y de la ficha del borrador.
No se han usado bases de datos, publicación, despliegue ni geocodificación.
