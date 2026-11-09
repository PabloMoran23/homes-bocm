# Quintana de la Serena — INE 06109, Badajoz

Investigación y extracción real: 2026-11-09. Un único adaptador, sin cambios compartidos ni dependencias nuevas.

## Fuentes descubiertas y selección

- Portal oficial municipal: https://quintanadelaserena.org/ . Identifica el Ayuntamiento en Plaza de España, Quintana de la Serena, Badajoz y enlaza la sede electrónica y los inventarios de actas. La petición directa con requests devolvió HTTP 403; el navegador de investigación pudo leer el portal. No se utiliza como fuente del parser.
- https://quintanadelaserena.org/ayuntamiento/documentos-on-line/ ofrece comunicación previa, presupuesto y solicitud de licencia de obras: son formularios, no concesiones, y se excluyen.
- La oficina técnica de la Mancomunidad incluye Quintana entre los municipios con PGM y remite a SITEX: https://mancomunidaddelaserena.com/urbanismo-en-la-comarca/ . Es una pista de descubrimiento, no prueba de vigencia: su texto territorial puede estar desactualizado.
- Fuente efectiva: Sistema de Información Territorial de Extremadura, Junta de Extremadura, https://sitex.juntaex.es/SITEX/planeamiento . Inventario público y fichas detalladas oficiales. Es una fuente autonómica sobre planeamiento municipal, no un registro municipal de licencias. `proyectos.source: ayuntamiento` conserva la categoría disponible en el contrato del repositorio; cada registro identifica expresamente `organismo_fuente: Junta de Extremadura — SITEX`.

## Protocolo y cobertura

El HTML público de consulta expone el selector municipal: Quintana de la Serena tiene ID interno SITEX **154**, distinto de su INE **06109**. El JavaScript del portal usa un Ajax.Updater para obtener el árbol. Se reproduce únicamente esa consulta pública de lectura:

`POST https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat`, cuerpo `municipioseleccionado=154`, cabecera `X-Requested-With: XMLHttpRequest`.

El parámetro por GET no selecciona el municipio. La respuesta POST marca tanto la opción vacía como Quintana como seleccionadas; se valida la opción seleccionada no vacía. El árbol completo viene en una respuesta, sin paginación observada. El adaptador rechaza marcadores de paginación para evitar producir una extracción incompleta si cambia el sitio. No hay límite artificial de registros ni lista de expedientes precargada.

Se descubren los enlaces `a.unenlaceafiguradeplaneamiento`, con IDs en `onclick` a `/SITEX/ptofiguras/viewsigcat/{id}`. Se selecciona planeamiento municipal PGM/NNSS/PDSU marcado **Vigente** o **En trámite**. Se excluyen los planes territoriales, incluso los mostrados en el árbol municipal, y el histórico **No vigente**. Cada ficha se verifica de nuevo por ámbito territorial y estado. Un cambio de formato, municipio equivocado, estado desconocido o inventario vacío causa error antes de sustituir el JSONL.

Resultado real: **7 instrumentos**, **47 enlaces documentales**:

| Referencia SITEX | Ficha | Estado fuente | Aprobación definitiva | Publicación AD |
| --- | --- | --- | --- | --- |
| PGM | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37335 | Vigente | 2010-02-15 | 2010-06-17 |
| PGM.M-001 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37284 | Vigente | 2012-05-31 | 2012-07-24 |
| PGM.M-002 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37325 | Vigente | 2013-10-31 | 2014-02-25 |
| PGM.M-003 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37404 | Vigente | 2014-06-26 | 2014-10-15 |
| PGM.M-005 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39705 | Vigente | 2020-12-21 | 2021-03-22 |
| PGM.M-006 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40086 | Vigente | 2022-02-24 | 2022-06-03 |
| PGM.M-004 | https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/39696 | En trámite | Sin dato | Sin dato |

Los números administrativos y los números del título no siempre coinciden: por ejemplo, PGM.M-006 corresponde a la modificación nº 7/2020. Se conservan ambos tal como aparecen, sin renumerarlos. La modificación en trámite trata la creación de dos sectores industriales y dotacionales; no se presenta como aprobada ni ejecutada.

## Semántica y límites

Un registro por ficha/instrumento; memoria, normativa, planos y anuncios de sus trámites se agrupan en `documentos`, deduplicados por URL y con la ficha de procedencia en `source_url`. Se conservan los enlaces originales, incluidos los HTTP históricos del DOE/BOP. Los documentos no se convierten en proyectos independientes. La ficha PGM.M-004 ofrece un anuncio inicial pero no un paquete técnico descargable; se conserva el enlace disponible y no se inventa el paquete.

`fecha_aprob` procede exclusivamente del campo **Fecha AD**; `fecha_publicacion` del campo **Fecha de publicación AD**. No se toman fechas de CMS, de publicación inicial ni de depósito como acuerdos de aprobación. No se introduce una fecha genérica ni se deduce `fecha_acuerdo`. Se retienen los metadatos etiquetados de la ficha. `estado_fuente` conserva el estado declarado por SITEX, sin interpretar que las obras estén en ejecución. La vigencia no se comprueba jurídicamente contra todos los diarios oficiales.

Cobertura parcial: inventario actual de planeamiento municipal vigente o en trámite, no todas las obras físicas, proyectos municipales o expedientes históricos. No hay extracción de licencias concedidas. Sin coordenadas, geometría o geocodificación inventadas; `publication_ready: false`, `geometry_status: unavailable`. Manifest con `licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`. La actualización vuelve a consultar el inventario completo; no usa fechas de publicación como cursor.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_quintana_de_la_serena -v`: **6 tests correctos**. Cubren selección municipal, exclusión territorial/histórica, deduplicación, paginación inesperada, identidad de ficha, fechas distintas y ausentes, aislamiento documental entre instrumentos y actualización completa mediante el cargador del manifest.

Extracción real mediante `load_manifest('quintana-de-la-serena')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['evidence_dir']='evidence'` para guardar capturas. El cargador aplica también la política compartida de entidades. Sin base de datos ni publicación.

Evidencia no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory.html`, `evidence/instrument-*.html`, captura de la página de consulta y muestra documental `evidence/sample-memoria-PGM-M003.pdf`. La muestra enlazada desde la ficha 37404, https://sitex.juntaex.es/SITEX/ptofiguras/downloaddocumento/797 , respondió HTTP 200, `application/octet-stream`, 9.722.602 bytes y firma `%PDF-1.3`. Se verificó una descarga completa; no se afirma haber descargado o validado todos los 47 documentos. El scraper extrae los metadatos y enlaces, sin interpretar el contenido binario.
