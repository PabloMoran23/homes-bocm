# Alagón (Zaragoza), INE 50008

Verificación en vivo: 2026-11-09. Adaptador único de planeamiento municipal.
Se revisaron primero `portal.py`, `registry.py`, `manifest.py` y los ejemplos
Chipiona y Hernani. El manifiesto usa el esquema existente, Aragón, Zaragoza y
`codigo_ine: '50008'`; licencias y programación deshabilitadas, sin jitter.

## Descubrimiento y fuente oficial

La página municipal vigente https://alagon.es/areas/urbanismo/ contiene el enlace
«ACCESO AL PLAN GENERAL DE ORDENACIÓN URBANA», que dirige a
https://alagon.sedelectronica.es/transparency/be3ffd61-0a97-41f8-8f37-589be87fba47/.
Esta carpeta contiene 7.1 Planeamiento (91 documentos), 7.2 Normativa (4),
7.3 Modelos de solicitudes (15) y 7.4 Expedientes en información pública (0).
Se extrae únicamente 7.1, descubierta desde ese enlace municipal en cada ejecución.
La página https://alagon.es/ventanilla/impresos-municipales/ es un inventario de
formularios, incluyendo solicitudes de licencia: no acredita concesiones.
No se convierten esos formularios, noticias ni anuncios de contratación en proyectos.

El inventario público de planeamiento es
https://alagon.sedelectronica.es/transparency/cea53cb0-4720-401e-885f-20088d10cc2d/.
La navegación utiliza acciones Wicket GET con sesión pública efímera: para carpetas
el servidor responde con redirección a una URL canónica UUID. No requiere identidad
ni acceso autenticado. El adaptador no conserva las acciones efímeras como IDs.

## Cobertura y agrupación verificadas

| Instrumento / URL oficial | Documentos retenidos |
| --- | ---: |
| [Texto refundido PGOU, acuerdo CPUZ 13/11/2018](https://alagon.sedelectronica.es/transparency/9546618d-f336-4d4d-b4ed-5fab3dcaab7b/) | 55 |
| [Estudio de detalle para ordenación de alturas de parcela pública destinada a equipamiento docente](https://alagon.sedelectronica.es/transparency/9b2c5d9f-66e3-46a5-8705-a4c0c447a3f9/) | 13 |
| [Aprobación inicial modificación aislada 5 PGOU](https://alagon.sedelectronica.es/transparency/07e6190f-e942-4dcb-a417-a7adc9ad26f3/) | 9 |
| [Aprobación inicial modificación aislada 6 PGOU](https://alagon.sedelectronica.es/transparency/111695b3-d5e0-421d-94ac-c6091a664b33/) | 13 |

Resultado: **4 instrumentos reales, 90 enlaces documentales** con título original,
URL estable de previsualización e inventario de procedencia. Memorias, planos,
informes, certificados y anuncios del mismo expediente forman un solo registro.
Los IDs derivan del UUID de carpeta, no del título ni del orden de extracción.

El documento raíz [1.5 Catálogo](https://alagon.sedelectronica.es/preview-document/001ce1d7-c198-441b-b9b4-b9049a30bc71)
se enumera pero no se atribuye al PGOU sin evidencia suficiente: figura en
`unassigned_documents` del resultado y de validation.json. No genera un proyecto
separado. Así quedan contabilizados los **91 documentos** anunciados por 7.1.

La primera página muestra diez documentos como máximo. Se recorren todos los
botones «Mostrar más» mediante respuestas XML Wicket y sus componentes HTML,
incluidas acciones cuya URL se reutiliza en páginas sucesivas. El recorrido solo
termina al desaparecer el botón; se exige progreso, se contrastan los contadores
recursivos de todas las carpetas y se falla ante conteo incompleto, documentos
sin agrupación revisada o cambios de estructura. Un límite de seguridad de 300
peticiones falla explícitamente, sin escribir resultados parciales. La escritura
JSONL solo reemplaza el destino después de completar y validar el inventario.

## Fechas, estado y límites

La única fecha estructurada es `fecha_acuerdo: 2018-11-13`, expresamente indicada
en el título del PGOU. Se conserva el texto y URL que acreditan su significado.
No se usa la hora actual de la sede ni fechas de nombres de archivos como fechas
de publicación, aprobación o acuerdo. Las modificaciones 5 y 6 se marcan como
aprobación inicial por el título de carpeta; no se infiere aprobación definitiva
ni estado actual a partir de documentos adjuntos. El estudio de detalle conserva
su título sin inferir fase. Los cuerpos documentales no se interpretan.

Cobertura parcial: instantánea del inventario público municipal de planeamiento,
no histórico exhaustivo, censo de obras ejecutadas ni registro de licencias.
La mera disponibilidad de una carpeta no certifica vigencia jurídica. No hay
geometría, coordenadas ni CRS verificados por instrumento. El visor regional SIUa
(https://idearagon.aragon.es/SIUa/visor) apareció en la investigación pero no se
verificó una correspondencia de geometrías con estos expedientes, y no se utiliza
como fuente de coordenadas. `geometry_status: unavailable`,
`publication_ready: false`, sin geocodificación ni centroides inventados.

## Validación reproducible y evidencia local

Runtime utilizado (sin instalaciones):
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_alagon -v` — **4 pruebas pasan**.
Cubren agrupación/deduplicación, fecha de acuerdo separada de publicación,
rechazo de formularios y URLs ajenas, paginación completa con acción repetida,
fallos atómicos por falta de progreso/conteo incompleto, manifiesto y licencias
vacías. Los fixtures son sintéticos y están incluidos en el archivo de pruebas;
ninguna prueba depende de evidencia local ni de conexión.

Extracción real mediante `load_manifest('alagon')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir'] = 'evidence'` para capturas opcionales.
La integración con el registro compartido se ejecutó sin modificarlo.
`update_proyectos` vuelve a enumerar la instantánea completa; no avanza una fecha
incremental ni altera el archivo de estado.

Evidencia no destinada a commit en `evidence/`: `proyectos.jsonl` (4 registros),
`validation.json` (conteos, URLs, catálogo no atribuido, limitaciones y resultado
de entity_policy), capturas `live-*.html/xml` de todas las peticiones de extracción,
y capturas exploratorias del inventario. No se ejecutaron orquestadores, publicación,
sincronizaciones, herramientas de despliegue ni operaciones remotas de Git.

Además, un enlace documental por instrumento devolvió HTTP 200 y una previsualización
con iframe PDF oficial; capturas `preview-0.html` a `preview-3.html` y comprobaciones
en `document_preview_checks` de validation.json. No se verificaron individualmente
las 90 descargas ni se extrajo el texto de sus PDFs.
