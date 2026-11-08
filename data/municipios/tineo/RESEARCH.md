# Tineo — INE 33073, Asturias

Revisión y extracción real: 2026-11-08. Adaptador único:
`municipio.adapters.tineo:TineoAyuntamientoAdapter`.

## Descubrimiento y alcance

La web oficial publica estos inventarios, consultados por HTTP con respuesta 200:

- [Instrumentos urbanísticos en tramitación](https://www.tineo.es/instrumentos-urbanisticos-en-tramitacion): fuente del adaptador. Página estática de contenido Liferay, sin paginación en la captura examinada.
- [Urbanismo y vivienda](https://www.tineo.es/urbanismo-y-vivienda): PGOU, tomos y otros instrumentos, incluidos documentos históricos. Se revisó para descubrir el contexto; no se integra en este extractor.
- [Catálogo urbanístico](https://www.tineo.es/catalogo-urbanistico): publicación BOPA, memoria y fichas, tampoco integrado.
- [Normativa urbanística](https://www.tineo.es/normativa-urbanistica): enlaza el registro regional y el visor. La consulta a `https://www28.asturias.es/rpgur/action/publico/welcome` falló por conexión. El enlace municipal del visor `http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php` redirige a `https://sigvisor.asturias.es/visorurbanismo/` (200). No se verificó una geometría vectorial vinculable por expediente.

Cobertura **parcial**, limitada al inventario municipal en tramitación tal como está publicado. No representa todo el planeamiento vigente, todo el histórico ni todos los proyectos u obras del municipio. No se extraen noticias, contratos, formularios ni licencias concedidas.

## Instrumentos y documentos

La extracción produce **5 instrumentos y 9 enlaces documentales**, conservando los títulos y URL completos con su página de procedencia:

| Instrumento | Documentos | Capturas locales |
| --- | --- | --- |
| Unidad de actuación Camino de San Roque | Anuncio DOCX y proyecto diligenciado PDF | document-0.docx, document-1.pdf |
| Delimitación en Vaqueiros de Alzada 6, Navelgas | Anuncio DOCX y proyecto diligenciado PDF | document-2.docx, document-3.pdf |
| ALISEDA: delimitación de unidad de actuación en San Roque | Resolución y solicitud concreta con documentación de la delimitación | document-4.pdf, document-5.pdf |
| Modificación PGOU Venta de Quildán | Documento de aprobación inicial, diciembre 2021 | document-6.pdf |
| Modificación PGOU en finca 1723601QJ1012S0001UJ, El Crucero | Anuncio de aprobación inicial y propuesta de modificación puntual | document-7.pdf, document-8.pdf |

Los nueve documentos se descargaron realmente, todos con HTTP 200 y contenido PDF o DOCX. Se conservaron y se extrajo texto de los PDF mediante `pdftotext` y de los DOCX mediante `zipfile`/XML, sin instalar software. El PDF de propuesta FARO es escaneado: no se obtuvo texto; se conserva el enlace y el anuncio legible.

El HTML sitúa Venta de Quildán dentro del mismo `ul` que ALISEDA. La portada de su PDF dice «MODIFICACIÓN DEL PLAN GENERAL DE ORDENACIÓN DE TINEO», Venta de Quildán y diciembre 2021; no pertenece a la delimitación de ALISEDA. El parser separa este documento en un instrumento propio. Su fase se expresa como **documento de aprobación inicial**, sin afirmar que se haya adoptado un acuerdo. La solicitud ALISEDA es documentación de un expediente concreto acompañado de su resolución; no un formulario genérico ni una licencia concedida.

Los IDs derivan del primer enlace documental sin el timestamp variable Liferay. Los documentos repetidos dentro de un instrumento se deduplican. Una asignación del mismo documento a instrumentos distintos provoca error. Los documentos no generan registros adicionales, salvo el instrumento independiente de Venta de Quildán verificado en su portada.

## Fechas y actualidad administrativa

El inventario no muestra fechas de publicación ni acuerdo. Todos los campos de fecha del extractor quedan nulos; no se interpretan `?t=...`, fecha de firma, fecha del proyecto ni fecha de descarga como publicación. La lectura de documentos durante la investigación confirmó:

- Camino de San Roque y Vaqueiros: resolución de Alcaldía de **10 de abril de 2024**; anuncios fechados **12 de abril de 2024**. La diligencia de los proyectos es posterior. Son significados diferentes; no se trasladan automáticamente al campo genérico de fecha.
- FARO: anuncio firmado el **10 de marzo de 2025**; narra sesión plenaria del **27 de febrero de 2025**. Ninguna de ellas es una fecha de publicación verificada en el inventario.
- Venta de Quildán: **diciembre 2021** es la versión del documento, sin día ni acuerdo acreditado por esa portada.

Las fases de los otros cuatro registros reflejan exclusivamente el texto del inventario. La búsqueda oficial también devolvió una disposición posterior para FARO, referencia BOPA **2025-09508**, de 24/11/2025, en [miPrincipado](https://miprincipado.asturias.es/ast/bopa/disposiciones?_pa_sede_bopa_web_portlet_SedeBopaDispositionWeb_mvcRenderCommandName=%2Fdisposition%2Fdetail&p_p_id=pa_sede_bopa_web_portlet_SedeBopaDispositionWeb&p_p_lifecycle=0&p_r_p_dispositionDate=24%2F11%2F2025&p_r_p_dispositionReference=2025-09508&p_r_p_dispositionText=2025-09508). No se incorpora como otro proyecto ni se usa para actualizar la fase. Por tanto, **no se garantiza que “en tramitación” o “aprobación inicial” sea la última situación administrativa**. Se conserva `fase_fuente` para explicitar este límite.

## Validación y seguridad de cobertura

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_tineo -v` (5 pruebas): separación de instrumentos, procedencia, fechas nulas, IDs estables, deduplicación, rechazo de paginación y estructuras desconocidas, preservación del fichero anterior ante fallo y licencias vacías. También se carga el manifiesto.

Se ejecutó `load_portal_adapter(load_manifest('tineo')).backfill_proyectos(...)` con captura activada únicamente en configuración local. Resultado real: 5 registros, 9 documentos. Evidencias locales en `evidence/proyectos.jsonl`, `evidence/validation.json`, HTML de las cuatro páginas revisadas, `live-inventory.html` y documentos/textos de la tabla. La validación incluye URL de fuente y documentos y limitaciones. No se incluyen las evidencias como archivos fuente.

El extractor recorre todos los grupos y enlaces de la página, sin límites que trunquen el inventario. Si aparece paginación reconocible, falta el contenido, desaparecen los documentos o cambia la estructura fuera de las formas admitidas, falla antes de reemplazar la salida. Un inventario vacío requiere revisión. `update_proyectos` refresca la instantánea completa del alcance, sin cursor ni eliminación externa.

`geometry_status: unavailable`: no se inventan coordenadas, centroides, CRS ni polígonos a partir de planos. `publication_ready: false`. `schedule.enabled: false`, `licencias.enabled: false`, `geocode.jitter_missing: false`. Sin cambios compartidos, dependencias nuevas, base de datos ni publicación.
