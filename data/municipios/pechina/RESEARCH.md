# Pechina (Almería), INE 04074

Investigación: 9 de noviembre de 2026. Adaptador exclusivo para este municipio.

## Inventario oficial y alcance

Fuente recorrida: https://www.pechina.es/Servicios/cmsdipro/index.nsf/tablon_view.xsp?p=Pechina

La rama **Territorio** del tablón municipal contiene el paquete documental de la adaptación parcial de las NN.SS. a la LOUA. El servidor utiliza XPages: las categorías se abren con POST y estado de formulario. Una petición GET con `expand` no despliega el contenido. El adaptador descubre las categorías, abre cada rama y sigue todos los controles «Siguiente». Los 21 identificadores documentales revisados protegen la agrupación: una adición desconocida exige revisión de procedencia y provoca error. Si faltan contenedores, se repite una página, cambia la estructura o se alcanza el límite de seguridad, falla antes de reemplazar la salida; no produce un histórico truncado.

Las fichas modernas identifican Ayuntamiento de Pechina / Secretaría / Territorio - Planeamiento Urbanístico. La descarga original se obtiene de la misma ficha en `/Servicios/Tablon/Tablon.nsf/0/<documentId>?OpenDocument`, que sí presenta los adjuntos `$FILE`. Se conservan las fichas, las URL originales, los títulos y todos los adjuntos por documento. La memoria original verificada responde HTTP 200, `application/pdf`, firma `%PDF-`; su portada dice «PGOU DE PECHINA. ADAPTACIÓN PARCIAL DE LAS NN.SS.» y «A. Memoria Justificativa y anexos». Sus revisiones técnicas de 2009 no equivalen a un acuerdo municipal.

Ficha de la memoria: https://www.pechina.es/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Pechina&documentId=B1995C861192B023C12577EA002D5464

Original: https://www.pechina.es/Servicios/Tablon/Tablon.nsf/0/B1995C861192B023C12577EA002D5464?OpenDocument

## Selección y semántica

Resultado vivo: **1 instrumento, 21 fichas, 22 enlaces a adjuntos**. Las 21 fichas indican publicación el 29/11/2010. Las siete pruebas pasan; el parser final se ha aplicado también a las 21 respuestas capturadas y su agrupación coincide con la extracción viva.

Un único instrumento, con memoria, normativa, resolución, planos, anexos y respuesta a alegaciones agrupados; cada documento no se convierte en un proyecto diferente. Se retienen las fechas explícitas de **publicación de cada ficha**, sin trasladarlas a la fecha del instrumento ni afirmar aprobación, vigencia o ejecución. No se infieren fases ni coordenadas. `publication_ready=false`, `geometry_status=unavailable`.

Cobertura parcial: paquete documental actualmente visible en la rama Territorio del tablón municipal heredado, no inventario exhaustivo de todas las obras o del planeamiento vigente. No se recorre el histórico ni se extraen licencias. Una consulta de fuentes actuales también localizó actuaciones posteriores en BOJA (por ejemplo, modificación 1/2017, Camino del Molino Alto, anuncio en BOJA de 18/01/2023) y una evaluación ambiental de modificación 1/2025 en el portal de la Junta. Esas fuentes no forman parte de esta extracción ni justifican atribuir vigencia actual al paquete antiguo.

Se revisaron también el catálogo de formularios y la sede electrónica: una solicitud/comunicación urbanística no acredita una licencia concedida. Las noticias y anuncios de contratación no se usan como actuaciones. La infraestructura Diputación comparte contenidos entre entidades: el dominio `pechina.es` por sí solo no prueba pertenencia a Pechina; se comprueban el parámetro municipal del inventario y el órgano de cada ficha.

## Verificación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_pechina -v`.

Extracción: cargar `load_manifest('pechina')`, resolver con `load_portal_adapter(manifest)` y ejecutar `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. La opción local `portal.config.capture_dir` permite guardar las respuestas HTML públicas. `update_proyectos` hace el mismo refresco completo sin modificar estado incremental; las licencias devuelven una salida vacía y desactivada.

Evidencia local no versionada en `evidence/`: registros reales en `proyectos.jsonl`, recuentos/URL/limitaciones en `validation.json`, respuestas HTML en `live/`, memoria PDF y su texto extraído. No se ejecutan publicación, geocodificación, bases de datos ni sincronización.
