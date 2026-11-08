# Caldas de Reis — INE 36005, Pontevedra, Galicia

Investigación y extracción real: 2026-11-07. Un único adaptador municipal, sin cambios de dependencias ni código compartido.

## Fuentes descubiertas y selección

- Página municipal de urbanismo: https://caldasdereis.gal/urbanismo_c.php . El índice web consultado muestra formularios de solicitudes/comunicaciones, una referencia al PXOM provisional de 16-03-2016 y un enlace al inventario urbanístico de la Xunta. La petición directa desde este entorno agotó el tiempo de conexión. Los formularios no acreditan licencias concedidas y no se extraen. Tampoco se usan noticias o anuncios de contratación.
- Inventario autonómico oficial: https://siotuga.xunta.gal/siotuga/urb . La fila exacta INE 36005, Caldas de Reis, enlaza a https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36005 . Publica el PXOM con aprobación 2018-10-11.
- El portal documental alternativo https://www.pxomcaldas.com/ apareció en la investigación; el acceso con navegador devolvió 403. No se depende de él ni se mezclan versiones de ese portal.

Se utiliza SIOTUGA, información mantenida y publicada por la Xunta de Galicia, no una copia privada. El campo de manifest `proyectos.source: ayuntamiento` selecciona el flujo de adaptadores del repositorio; la fuente material de cada registro es explícitamente `xunta_galicia`.

## Inventario y protocolo reproducible

El HTML municipal contiene el selector `36005 = Caldas de Reis` y un nonce de formulario público anónimo. El JavaScript público `assets/inventario/controls.min.js?2.5.0` muestra las consultas del navegador:

1. POST `https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php`, parámetros `id=36005`, `idclase=14`, `13`, `16`, `18` y nonce público de esa sesión. Categorías: general, desarrollo, histórico y delimitación de núcleo rural. Se consultan las cuatro, aunque estén vacías.
2. POST `https://siotuga.xunta.gal/siotuga/assets/inventario/getIOTPU.php`, `iddoc=<id>`, `idp=0`, idioma del formulario y nonce, para cada instrumento.
3. Los documentos se construyen exactamente como el navegador: `filesroot + folder + /documents/ + pathesperado`, relativos a la raíz SIOTUGA.

Las consultas devuelven arrays completos; DataTables pagina en el cliente. No hay límite de filas ni recorte del array. Un cambio a respuesta con envoltorio/paginación provoca error, sin sustituir la salida previa. Los enlaces de `source_urls` con parámetros de consulta identifican las consultas; su método real es POST, como se explica aquí y en `detalle_fuente`.

Cada ID documental del inventario representa un instrumento, no cada PDF o plano. Se conservan todos los enlaces y sus grupos. Se valida identidad de municipio/carpeta e ID en cada ficha. Los nombres de archivos antiguos pueden tener numeración distinta del ID de ficha (por ejemplo `0733pl001.jpg` en la ficha 22776); se respeta la relación explícita de la fuente.

## Resultado real y semántica

15 instrumentos: 7 de planeamiento general, 7 de desarrollo y 1 histórico; delimitaciones rurales: respuesta `null`. Incluye PXOM (28055), corrección de localización del petróglifo das Cortiñas (28316), modificaciones en Godos/A Pena/Pais Pasionistas, cambios de uso dotacional, plan parcial SAU-1 Eirín, PEID parcela SX-EQ E-151 (28546), estudios de detalle y normas subsidiarias históricas (22775).

462 enlaces documentales agrupados en esos registros. Cinco fichas no ofrecen componentes: 25613, 24647, 24649, 24648 y 27471; se mantienen como instrumentos reales con `documentos_status: unavailable_in_inventory`, sin inventar documentos. No se infiere vigencia por estar inventariados: las normas de 1995 se etiquetan en la categoría histórica y las modificaciones anteriores al PXOM tampoco se afirman vigentes.

`fechaaddef` se conserva como `fecha_aprob`. DOG, BOP y publicación de normativa en BOP se guardan separadamente; no se transforman en fecha de acuerdo ni se escoge una fecha genérica de publicación. No hay fechas deducidas de noticias, CMS o nombres de archivo. No se deducen fases ni coordenadas. `publication_ready: false`, `geometry_status: unavailable`. Licencias, programación y jitter desactivados en manifest.

Cobertura parcial del universo municipal: solo estas cuatro clases de planeamiento SIOTUGA; no todas las obras físicas, ni licencias, ni tramitación pendiente que aún no esté inventariada. La consulta territorial supramunicipal, examinada en investigación, mezcla directrices/planes de toda Galicia y proyectos de varios concellos; queda fuera de este alcance y no se representa como proyectos exclusivamente municipales.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_caldas_de_reis -v`: seis pruebas correctas (agrupación, fechas, archivos antiguos, documentos ausentes, identidad, arrays completos sin truncamiento, contrato del manifest y recorrido de cuatro categorías/fichas mediante transporte simulado).
- Ejecución real de `CaldasDeReisAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir: evidence/captures`: **15 registros**.
- PDF de índice del PEID `https://siotuga.xunta.gal/siotuga/documentos/urbanismo/CALDASDEREIS/documents/28546me000.pdf`: HTTP 200, application/pdf, firma `%PDF-`, 108448 bytes. Solo se verificó esta descarga, no todos los enlaces.

`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML/JSON y PDF quedan locales, fuera de los cuatro archivos fuente. Las capturas de la ejecución omiten el nonce público del HTML. No se ha utilizado base de datos, geocodificación, publicación ni despliegue.
