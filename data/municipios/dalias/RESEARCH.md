# Dalías — Almería — INE 04038

Investigación y extracción en vivo: 9 de noviembre de 2026. Python utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y descubrimiento

Inventario municipal público [Territorio](https://www.dalias.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_categoria1.xsp?p=Dalias&cat=Territorio), perteneciente al Ayuntamiento de Dalías (CIF P0403800F, Dalías, Almería, según su pie). Se consultaron antes el contrato `municipio/adapters/portal.py`, el cargador `municipio/manifest.py`, el registro y los ejemplos Chipiona/Hernani.

Los resultados de búsqueda también remiten a fichas con `p=SedeDalias` alojadas en Dipalme. Las peticiones directas de esas variantes redirigieron a login: no se accedió al sistema restringido. La variante pública `www.dalias.es`, `p=Dalias`, sirve las mismas fichas mediante acceso anónimo.

El listado XPages empieza con categorías plegadas. El adaptador obtiene la página, conserva sesión y campos ocultos del formulario público y envía los eventos de despliegue de categorías (solo consultas públicas). Repite hasta que no quedan categorías plegadas. Los iconos `expand.gif` y etiquetas españolas/inglesas permiten reconocer el estado independientemente del idioma del cliente. Se comprueba el inventario en cada respuesta. Una categoría que no se despliega, un cambio de estructura o paginación detectada causan error antes de escribir resultados. La consulta observada se desplegó por completo en siete operaciones, sin paginación. No hay límite silencioso de registros: el límite defensivo de operaciones también produce error.

## Cobertura y agrupación

Las 14 fichas actuales corresponden a 10 instrumentos/proyectos:

- Normas Subsidiarias de Dalías: expediente administrativo, memoria/documentación técnica y planos en un solo registro.
- Adaptación Parcial NNSS: expediente, documento técnico y planos en otro registro.
- Tres correcciones: PGOU, alineaciones de calle Olmo y antiguas escuelas de Celín.
- Cuatro estudios de detalle de alineaciones: calle Santo Cristo 37, 46, 11 y 44.
- Instalación solar fotovoltaica de autoconsumo en suelo rústico: proyecto de actuación y anuncios de aprobación, incluidos los adjuntos de la actualización de la ficha.

Las categorías de NNSS y su adaptación definen las dos agrupaciones documentales; las demás fichas se identifican por su `documentId` oficial y permanecen separadas. Se conservan títulos originales de las fichas en `fichas`, su categoría, URL, fecha de publicación y todos los enlaces documentales con procedencia en `documentos`. Los enlaces duplicados de descarga de cada adjunto no se cuentan dos veces. El proyecto solar se admite porque contiene el documento «Proyecto de Actuacion», no por ser una noticia o anuncio. No se extraen formularios, ordenanzas, contratación ni licencias concedidas. Una nueva categoría de planeamiento requiere revisión explícita.

Cobertura limitada al inventario público actual de Territorio: no es una relación exhaustiva de obras físicas ni de expedientes históricos, ni certifica la vigencia jurídica del planeamiento. Las correcciones publicadas son instrumentos documentados; no se desglosan sus posibles actuaciones internas como proyectos ficticios.

## Fechas, localización y publicación

`Publicado` se almacena como `fecha_publicacion` en cada ficha; sus adjuntos conservan esta referencia como `fecha_publicacion_ficha`, sin atribuirles una fecha de publicación propia. No se convierte en fecha de acuerdo, aprobación, concesión o inicio de obras. Los rótulos originales de los documentos que mencionan aprobación se retienen sin deducir fechas o estados. El dato de modificación del CMS tampoco se usa como fecha de aprobación. Los PDF están enlazados, sin interpretación exhaustiva de su contenido.

No se inventan coordenadas, geometrías, importes ni números de expediente. Se marca `geometry_status: unavailable` y `publication_ready: false`. Manifiesto: `licencias.enabled: false`, `schedule.enabled: false`, `geocode.jitter_missing: false`. La actualización ejecuta una instantánea completa, para detectar también nuevos adjuntos de instrumentos antiguos; no utiliza una fecha máxima que descarte documentos.

## Verificación reproducible

Pruebas: `python -m unittest municipio.test_dalias -v`: nueve pruebas correctas. Incluyen agrupación y aislamiento documental, fechas explícitas, rechazo de formularios y fichas sin documentos, identificación del municipio, proyecto solar con documento técnico, categorías desconocidas, host de enlaces, duplicados, estructura perdida, categorías plegadas, paginación y conservación de adjuntos archivados.

Extracción real mediante `load_manifest('dalias')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['evidence_dir']='evidence/live'`. Solo escrituras locales. Evidencia no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML del inventario inicial y sus siete expansiones, y las 14 fichas en `evidence/live/`. `validation.json` contiene el recuento, URLs consultadas, limitaciones y resultado del guardado con la política compartida de entidades.

Resultado final de la ejecución: **10 registros, 63 enlaces documentales, 14 fichas**. Los registros declaran `source_entity_type: documento`: representan instrumentos/proyectos documentados, sin reclamar una identidad de actividad ejecutada ni concesión de licencia. La política compartida los clasifica como documentos y no como entidades desconocidas.

Se comprobó además un PDF real: el BOP del proyecto solar (HTTP 200, `application/pdf`, firma `%PDF-`, 118.841 bytes). Capturas: `evidence/solar-bop.pdf`, `evidence/solar-bop.txt` y `evidence/pdf-validation.json`. Corrobora la instalación de autoconsumo para bombeo y elevación de agua de la Comunidad de Regantes Los Llanos de Dalías, parcelas 37/polígono 5 y 109/polígono 4. El boletín está fechado el **25/08/2025**, menciona acuerdo del Pleno del **01/08/2025**, y el anuncio se firma el **20/08/2025**. Son fechas distintas de `Publicado: 21/08/2025` de la ficha. Se documenta aquí esta comprobación puntual; el parser no fija estas fechas como constantes ni presume las fechas de los demás instrumentos. El propio anuncio indica que el proyecto de actuación es necesario y previo a la licencia municipal: no demuestra una licencia concedida.

El BOP solar está en `archivadoanexos_1.nsf`, dentro del bloque de modificaciones de la ficha. El parser conserva también estos adjuntos con `archivado: true`; no elimina el historial enlazado por limitarse a `anexos.nsf`.
