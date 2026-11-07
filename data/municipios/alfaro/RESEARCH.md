# Alfaro — La Rioja — INE 26011

Investigación y extracción en vivo: 7 de noviembre de 2026.

## Fuentes oficiales descubiertas

La portada del [Ayuntamiento de Alfaro](https://alfaro.es/) enlaza tanto la
[Agenda Urbana municipal](https://alfaro.es/agendaurbana/) como el Plan General
Municipal en el SIU del Gobierno de La Rioja. El enlace municipal al SIU usa
HTTP y el código municipal provincial `011`; se comprobó su equivalente
[HTTPS](https://siu.larioja.org/mapa_municipio.php?cod_ine=011), que respondió
403 con una página de desafío JavaScript/cookies. No se ha eludido ese bloqueo
ni se afirma haber extraído el inventario completo de planeamiento reglado.

También se inspeccionaron la sección municipal de Urbanismo y Servicios
(organigrama, no inventario de expedientes), Transparencia y la sede electrónica.
Los formularios de trámites, contratos menores y anuncios de licitación no se
utilizan como proyectos ni como licencias concedidas. Las actas del pleno
aparecen como otra fuente documental posible, pero no se implementa su histórico.

La fuente implementada es el [catálogo de actuaciones del Plan de Acción de
Alfaro](https://alfaro.es/agendaurbana/plan-de-accion-alfaro/). Es un inventario
municipal accesible actualmente que conserva propuestas de la Agenda Urbana,
con fichas HTML específicas y documentación PDF. La disponibilidad actual del
catálogo no demuestra que las propuestas estén aprobadas, vigentes o ejecutadas.

## Cobertura implementada

Se descubrieron **19 acciones numeradas** y se extrajeron **6 actuaciones**:

| Acción | Actuación | Documentos agrupados |
| --- | --- | --- |
| 02 | Creación de itinerarios suelo no urbanizable | Ficha HTML y PDF Creación de red de itinerarios |
| 04 | Rehabilitación convento de la Concepción | Ficha HTML y PDF Rehabilitación del convento |
| 06 | PERI Cerámicas | Ficha HTML y PDF Sostenibilidad económica del PERI Cerámicas |
| 07 | PERI Palacio Ramirez | Ficha HTML y PDF PERI Palacio Remirez |
| 09 | Plan de movilidad urbana sostenible | Ficha HTML y PDF Estrategia de mobilidad urbana sostenible |
| 10 | PERI Zona cuevas | Ficha HTML; sin PDF específico localizado en el catálogo |

Los nombres Ramirez/Remirez y mobilidad reproducen las variantes de la fuente.
Los PDF son fichas de planificación/estudio asociadas: no se presentan como
acuerdos administrativos ni como aprobación de los instrumentos. Cada acción
es un único registro; sus documentos no generan actuaciones duplicadas.

Esta selección temática es deliberadamente parcial. Excluye las otras 13
acciones, que incluyen programas sociales, empleo, gobernanza y también otras
propuestas físicas/estratégicas como infraestructura verde, ARI Burgo, Ebro
Resilience y cohousing. No se declara exhaustividad municipal ni de todas las
actuaciones físicas de la Agenda. No se convierte el Plan de Acción genérico
en un proyecto sintético. Las seis propuestas tienen ámbito físico o contenido
de planificación específico y descripción propia en la fuente.

## Parser y semántica

El adaptador descubre las acciones mediante sus enlaces numerados, comprueba
la correspondencia número/URL y elimina enlaces repetidos del menú. Selecciona
por título temático y asocia los PDF del índice mediante sus nombres revisados,
sin construir URL de documentos inexistentes. Descarga cada ficha específica,
verifica su título y extrae exclusivamente la sección «Descripción de la acción».
Conserva los enlaces y la procedencia del índice en `documentos`/`inventory_url`.
El identificador usa el número de acción municipal, no el título cambiante.

No se emiten fechas de publicación, acuerdo o aprobación: ni las rutas de
subida de 2022 ni las marcas del CMS acreditan esos hechos. No se infiere una
fase administrativa desde el título PERI. `naturaleza` indica expresamente
propuesta de la Agenda; `publication_ready=false` y `geometry_status=unavailable`.
No se inventan coordenadas. El manifest desactiva licencias, programación y
jitter. No se verificó un registro de licencias concedidas.

El índice observado está completo en una página sin controles de paginación.
Si aparecen enlaces de página numerada o siguiente, el adaptador falla
explícitamente en lugar de truncar resultados. También falla ante índices
vacíos, documentos asociados desaparecidos, títulos discordantes o cambios de
estructura de la descripción. Las actualizaciones repiten la instantánea
completa; no prometen historial incremental ni bajas históricas. La escritura
del resultado solo ocurre después de completar todas las fichas seleccionadas.

## Verificación reproducible y evidencia local

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_alfaro -v`: **5 correctas**.
Cubren asociación de documentos por instrumento, deduplicación, exclusión de
programas/formularios/contratación, ausencia de fechas y geometría inferidas,
fallos de estructura/paginación, refresco completo, preservación de la salida
ante errores y flags del manifest.

Se ejecutó realmente `AlfaroAyuntamientoAdapter.backfill_proyectos` con
`config={'capture_dir': 'evidence/captures'}` y salida
`evidence/proyectos.jsonl`: **6 registros**. Se descargaron los cinco PDF
asociados: todos respondieron correctamente con firma `%PDF-`; se conservaron
los archivos completos (3.758.936 bytes en conjunto). La repetición del parser
sobre las siete capturas HTML del índice y fichas produjo exactamente los
mismos seis registros que la extracción en vivo.

`evidence/validation.json` contiene `live_records`, `source_urls`, limitaciones,
URLs finales, metadatos y SHA-256 de los PDF. `evidence/extraction_result.json`
conserva el resumen del adaptador. Se guardaron además la portada municipal y
la respuesta bloqueada del SIU en `evidence/captures/`. Toda la evidencia es
local y no forma parte de los cuatro archivos fuente entregables. No se han
usado bases de datos, credenciales, publicación ni despliegue.
