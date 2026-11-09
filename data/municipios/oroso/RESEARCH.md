# Oroso — INE 15060, A Coruña (Galicia)

Revisión y extracción en vivo: 2026-11-08. Un único adaptador municipal,
`municipio.adapters.oroso:OrosoAyuntamientoAdapter`. Se revisaron antes el contrato
`municipio/adapters/portal.py`, el cargador/esquema `municipio/manifest.py`, el
registro y los ejemplos de Hernani y Manlleu. No se modifican fuentes compartidas.

## Fuentes oficiales y descubrimiento

La web municipal vigente https://www.oroso.gal/ enlaza «Servizos → Urbanismo»:
https://www.oroso.gal/show_content.php?section=5&subsection=27
Esta página es el inventario documental utilizado, no una noticia seleccionada.
Contiene la descripción del PXOM, su fecha explícita de aprobación, un enlace al
archivo original y el modal de documentación de San Martiño II/Sector 10.

El enlace municipal al PXOM lleva a
https://www.concellooroso.com/pxom/index.htm . Aunque pertenece al dominio antiguo,
es la fuente documental enlazada actualmente por el Concello. El extractor descubre
y recorre sus marcos, enlaces HTML, mapas de imagen y fragmentos HTML literales de
`submenu[n]` del menú JavaScript. No ejecuta JavaScript. Se recorrieron **48 páginas
HTML del archivo**, más la página municipal vigente. Se guardaron respuestas HTTP
200 e índice URL/archivo/SHA256 en `evidence/captures/index.json`.

El mismo inventario enlaza la consulta regional:
https://siotuga.xunta.gal/siotuga/inventario . Se comprobó HTTP 200 y se capturó su
formulario municipal en `evidence/siotuga.html`. Es una fuente adicional de
expedientes originales y modificaciones, **no cubierta por este adaptador**. No se
presenta el archivo municipal como texto consolidado ni como historial completo.

## Registros y agrupación

La extracción real generó **3 instrumentos**, nunca un registro por PDF:

| Instrumento | Documentos únicos enlazados |
| --- | ---: |
| Plan Xeral de Ordenación Municipal de Oroso original | 101 |
| Plan Parcial do Área de Reparto Número 10, Polígono Empresarial San Martiño II | 18 |
| Proxecto de reparcelación do Sector 10 | 8 |

Cada documento conserva URL, título, rótulos alternativos y páginas de procedencia.
La página municipal enlaza el mismo `polsmar/planos/o_viario.pdf` con los rótulos
«I-13 LIMITACIONS…» y «ORDENACIÓN: COTAS-VIARIOS-PERFILES». Se conserva la anomalía
como dos rótulos de una sola URL, sin inventar un PDF I-13. Los ZIP se conservan como
documentos enlazados; no se descomprimen ni se cuentan sus componentes.

Como verificación adicional se descargaron tres PDFs reales, todos HTTP 200 y con
firma PDF: `pxom/normativa/01.pdf`, `polsmar/memoria.pdf` y
`polsmar/reparcelacion/memoria.pdf`. Binarios, hashes y resultados están en evidence.
`pdftotext` sobre las primeras tres páginas confirma plan parcial del Sector 10,
Concello de Oroso como promotor, y memoria fechada **maio de 2008**. La memoria de
reparcelación indica **xuño de 2008, DOCUMENTO DE APROBACIÓN INICIAL**. Son fechas y
versiones de redacción documental: no justifican una fecha de acuerdo ni permiten
inferir aprobación definitiva de estos dos instrumentos. Estas observaciones son
verificación local; el adaptador extrae los índices HTML y conserva los enlaces,
no interpreta ni valida jurídicamente todo el contenido de los PDFs.

## Semántica y límites

La página vigente dice literalmente «PXOM), aprobado definitivamente na orde
16/02/05». Se registra `fecha_aprob: 2005-02-16` únicamente para el PXOM original,
con URL y cita de procedencia. Todas las fechas de publicación y acuerdo quedan
nulas, así como las fechas de aprobación de plan parcial y reparcelación. No se
utilizan el año del pie de página ni las fechas de documentos como publicación.
No se infiere el estado actual de tramitación de San Martiño II. Los IDs son
estables por instrumento, independientes del orden y número de documentos.

Cobertura parcial: documentación histórica publicada y enlazada actualmente en
Urbanismo; no toda la planificación, modificaciones regionales, obras municipales,
noticias ni contratación. Los formularios de licencias y la descripción de
funciones de Urbanismo no acreditan concesiones. `licencias.enabled: false` y los
métodos de licencias devuelven vacío con estado disabled.

No hay paginación en los índices revisados. Se recorren todos los HTML descubiertos
bajo `/pxom/`, evitando ciclos. Un enlace de siguiente página, un nuevo tipo de
enlace interno, cambio de sintaxis de submenú, error HTTP, falta de documentos o
más de 100 páginas provoca error antes de reemplazar el JSONL, nunca truncamiento
silencioso. Los adjuntos se conservan como enlaces; solo tres PDFs se descargaron
como comprobación adicional. Un futuro cambio de estructura requiere revisión.

## Geometría

`geometry_status: unavailable`. Existen planos PDF y la consulta/visor de SIOTUGA,
pero no se ha verificado una capa vectorial con geometrías enlazables a estos tres
instrumentos. No se extraen centroides ni se vectorizan planos. Coordenadas y
geometría nulas, `publication_ready: false`, `geocode.jitter_missing: false`.
No se afirma que no exista cartografía regional; queda fuera de la cobertura.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_oroso -v` — **7 pruebas pasan**:
agrupación/fechas, rechazo de contenido ausente y formularios, marcos/menús/mapas,
paginación y formatos imprevistos, recorrido completo con ciclos y deduplicación,
conservación del resultado previo ante fallo, manifest y licencias deshabilitadas.

Extracción real mediante `load_manifest('oroso')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con configuración
local `capture_dir=evidence/captures`. `evidence/validation.json` contiene
`live_records: 3`, todas las URLs recorridas, limitaciones y comprobaciones de PDFs.
Backfill e incremental refrescan la misma instantánea completa; no se avanza un
cursor que pueda ocultar páginas. `schedule.enabled: false`.
Evidencia local excluida del control de versiones. Sin publicación ni despliegue.
