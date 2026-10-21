# Contrato semántico municipal

`db/project_semantics.py` aplica el mismo contrato en `portal_proyecto_row`, en la guardia de `save_proyectos` y en `db/reprocess_project_semantics.py`. No necesita modelos, agentes ni una edición puntual de datos.

- `descripcion`, `resumen`, `resumen_contenido`, `bocm_resumen`: descripción original, con campo y URL de procedencia. Una copia del título no es descripción.
- `tipo`, `tipo_legal`, `tipo_figura`, `bocm_tipo_instrumento`: tipo de instrumento. Alias incompatibles producen desconocido.
- `fase`, `estado_tramitacion`, `bocm_estado_tramitacion`: fase administrativa explícita reconocida. Un tipo de instrumento o fase no reconocida produce NULL con motivo.
- `fecha_publicacion` / `fecha_publicación` / `bocm_pub_date`, `fecha_acuerdo` / `bocm_fecha_acuerdo`, `fecha_aprob` / `fecha_aprobacion`: tres significados distintos. Una fecha genérica nunca entra en ellos. Fechas inválidas o contradictorias producen NULL.
- Resumen factual: plantilla exclusivamente sobre hechos estructurados validados; cada cláusula identifica su hecho y éste apunta al campo original. No se extraen cifras desde prosa libre. Un registro con solo título conserva título, resumen NULL, estado `discovered` y motivo `missing_description_or_title_copy`.

Los derivados actuales están en `raw_features_json._semantic_contract`; la descripción fuente nunca se mezcla con el resumen factual. La tabla `homes.proyecto_semantica_version` conserva cada original y derivación por hash de fuente y versión de contrato/plantilla. La tabla se crea idempotentemente dentro de la transacción de ingesta (el rol de ingesta necesita permiso CREATE en homes). Una nueva regla requiere incrementar `CONTRACT_VERSION` o `TEMPLATE_VERSION`. Se conservan metadatos de otras guardias; `_entity_policy` no invalida el hash de contenido semántico.

`refresh-municipios.yml` ejecuta el reproceso diariamente antes del refresco municipal, con un límite de 20 minutos para este paso. El CLI pagina por identificador en lotes de 100 filas: cada lote tiene su conexión y transacción, y bloquea solo sus filas. Inserta el historial y actualiza los derivados en bloque. Omite fuentes/reglas sin cambios, conserva los originales y confirma cada lote antes de registrar su avance. Una excepción revierte solo el lote actual y falla el job; los lotes anteriores permanecen confirmados y se omiten al repetir. No crea proyectos ni activa clasificación/publicación durante el reproceso.

Para una comprobación acotada: `python db/reprocess_project_semantics.py --batch-size 5 --max-batches 1`. El resultado indica `complete=false` si el límite impide acreditar que se ha examinado todo el censo. Para el reproceso completo se omite `--max-batches`. El helper Python `replay(conn)` conserva la transacción del caller para integración y pruebas; el CLI usa `run_replay`, que confirma por lote.

El exportador conserva sus campos anteriores y añade `fechaPublicacion`, `descripcionFuente`, `resumenEvidencia`, `contenidoEstado` y `contenidoDesconocido`. `fechaAcuerdo` y `estadoTramitacion` usan el contrato municipal cuando existe.

## Validación

CI `project-semantics.yml` prueba alias y casos ambiguos por contrato, más PostgreSQL 16 aislado: ingesta repetida, eliminación de campos, cambio de fuente, cambio de plantilla, fallo transaccional y recuperación, cardinalidad de proyectos e historial. También reproduce una desconexión tras un lote confirmado y verifica repetición sin duplicados, rollback conjunto de historial/derivados y preservación de fechas, NULL y metadatos de otras políticas en el update masivo.

## Límites pendientes de #851

La versión 1 extrae hechos de campos del adaptador, no del texto completo de cada PDF. Un cambio de URL/documentación o de contenido del registro invalida el hash. Un PDF modificado bajo la misma URL sin cambio del registro necesita un monitor de hash documental para disparar este contrato; esta PR no implementa esa infraestructura. La siguiente revisión debe integrar ese disparador y parsers de documento con citas. La exportación aporta el estado de falta de descripción; la presentación específica de ese estado en la ficha web todavía requiere trabajo. Por esos motivos la PR referencia la issue y no la cierra.
