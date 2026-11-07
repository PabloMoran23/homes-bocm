# Bailén (Jaén), INE 23010

Investigación y extracción en vivo: 2026-11-07. Un único adaptador municipal, sin escritura externa.

## Autoridad y descubrimiento

La página oficial de la [Delegación de Urbanismo](https://ayto-bailen.com/urbanismo/) enlaza expresamente `http://www.pgoubailen.es/` como consulta del planeamiento digital. Se accede al mismo archivo por HTTPS en `https://pgoubailen.es/index.html`. El archivo se identifica como «Excmo. Ayuntamiento de Bailén. DELEGACIÓN DE URBANISMO». El enlace histórico a PUA incluye `provincia=23&muni=23010`, consistente con Bailén, Jaén. La captura municipal se conserva en `evidence/urbanismo.html`.

Se descubrieron y recorrieron las cuatro secciones actuales del menú:

- https://pgoubailen.es/index.html : PGOU, 16 documentos (memoria, normas, estudio económico, programa, anexo y paquetes cartográficos).
- https://pgoubailen.es/adaptacion_parcial.html : adaptación parcial a la LOUA, 19 documentos.
- https://pgoubailen.es/revisiones.html : revisión parcial del PGOU en suelo no urbanizable, 5 documentos.
- https://pgoubailen.es/modificaciones.html : modificación puntual de la norma X.6.4, 1 documento.

Resultado: **4 instrumentos y 41 enlaces documentales**, agrupados por instrumento, nunca un registro por plano. El índice externo «Modificaciones Puntuales desde 1/6/1995 hasta 17/7/06» no identifica expedientes individuales y no se convierte en proyecto. No hay paginación visible en estas cuatro secciones estáticas. El adaptador sigue el menú y continuaciones HTML, sin límite artificial de páginas; una paginación que no pueda interpretar produce error en lugar de omitirla. Cambios de estructura o secciones sin documentos también producen error.

La búsqueda identificó además https://pgombailen.es/ y su inventario del nuevo PGOM. Dos intentos directos durante esta tarea terminaron con `RemoteDisconnected`. Los resultados indexados de búsqueda no se utilizan como registros ni para afirmar aprobaciones. Por tanto, esta extracción **no incluye el nuevo PGOM**, ni constituye un inventario completo del planeamiento actual. La web municipal también publica formularios y noticias de licitación: no son licencias concedidas ni instrumentos documentados y quedan fuera del adaptador.

## Semántica y límites

Cada registro contiene la página de inventario, la página municipal de procedencia y los títulos/URLs de todos sus documentos. Los documentos son enlaces publicados, sin afirmar validación exhaustiva de su contenido o disponibilidad. Se comprobaron los primeros 1024 bytes del primer PDF de cada instrumento: los cuatro respondieron HTTP 200, `application/pdf`, firma `%PDF-`. Muestras y resultados en `evidence/document_*.bin` y `evidence/document_checks.json`. Los otros 37 enlaces no se descargaron ni se verificaron individualmente; algunos ZIP conservan codificación porcentual histórica.

La revisión indica expresamente «Aprobación inicial: Sesión plenaria de fecha 26-10-2012»: se registra como `fecha_acuerdo: 2012-10-26` y `fase: aprobación inicial`, con cita literal. El BOP de 13-11-2012 y Diario Jaén de 9-11-2012 son publicaciones del trámite y permanecen en `descripcion`, sin sustituir la fecha de acuerdo. No se asigna una fecha genérica ni se deducen fechas de nombres de archivos, años del plan o metadatos del servidor. Los otros tres registros no incluyen fechas ni fases inferidas. La aprobación inicial histórica no acredita la situación vigente.

No hay coordenadas ni geometría verificada: `geometry_status: unavailable`, `publication_ready: false`. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` son falsos. No se han verificado concesiones de licencias, ejecución material de obras, vigencia, derogaciones o acuerdos posteriores. La actualización relee el archivo completo; no es un incremental cronológico. El servidor declara ISO-8859-1 pero sirve UTF-8 con BOM; el adaptador prioriza UTF-8 estricto y admite ISO-8859-1 como alternativa.

## Reproducción y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_bailen -v` (6 correctas). Verifican agrupación y deduplicación documental, separación de revisiones, exclusión de índices genéricos, fechas explícitas, errores de estructura, paginación y recorrido real del contrato mediante transporte simulado.

La ejecución real carga `load_manifest('bailen')`, establece opcionalmente `manifest.portal.config['capture_dir'] = 'evidence/archive'`, crea el adaptador con `load_portal_adapter(manifest)` y llama a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se ejecutó mediante el registro compartido, incluida su anotación de política de entidades. No se modificó ningún módulo compartido. Capturas originales de las cuatro páginas en `evidence/archive/`; salida y resumen en `evidence/proyectos.jsonl`, `evidence/live_result.json` y `evidence/validation.json`. La evidencia es local y no forma parte de los cuatro archivos fuente.
