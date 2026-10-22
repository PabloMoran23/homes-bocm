# Contrato semántico municipal

`db/project_semantics.py` aplica el mismo contrato en `portal_proyecto_row`, en la guardia de `save_proyectos` y en `db/reprocess_project_semantics.py`. No necesita modelos, agentes ni una edición puntual de datos.

- `descripcion`, `resumen`, `resumen_contenido`, `bocm_resumen`: descripción original, con campo y URL de procedencia. Una copia del título no es descripción.
- `tipo`, `tipo_legal`, `tipo_figura`, `bocm_tipo_instrumento`: tipo de instrumento. Alias incompatibles producen desconocido.
- `fase`, `estado_tramitacion`, `bocm_estado_tramitacion`: fase administrativa explícita reconocida. Un tipo de instrumento o fase no reconocida produce NULL con motivo.
- `fecha_publicacion` / `fecha_publicación` / `bocm_pub_date`, `fecha_acuerdo` / `bocm_fecha_acuerdo`, `fecha_aprob` / `fecha_aprobacion`: tres significados distintos. Una fecha genérica nunca entra en ellos. Fechas inválidas o contradictorias producen NULL.
- Resumen factual: plantilla exclusivamente sobre hechos estructurados validados; cada cláusula identifica su hecho y éste apunta al campo original. No se extraen cifras desde prosa libre. Un registro con solo título conserva título, resumen NULL, estado `discovered` y motivo `missing_description_or_title_copy`.

Los derivados actuales están en `raw_features_json._semantic_contract`; la descripción fuente nunca se mezcla con el resumen factual. La tabla `homes.proyecto_semantica_version` conserva cada original y derivación por hash de fuente y versión de contrato/plantilla. La tabla se crea idempotentemente dentro de la transacción de ingesta (el rol de ingesta necesita permiso CREATE en homes). Una nueva regla requiere incrementar `CONTRACT_VERSION` o `TEMPLATE_VERSION`. Se conservan metadatos de otras guardias; `_entity_policy` no invalida el hash de contenido semántico.

`refresh-municipios.yml` ejecuta el reproceso diariamente antes del refresco municipal. El reproceso bloquea los registros seleccionados, omite fuentes/reglas sin cambios, actualiza solo columnas semánticas y metadatos y conserva las versiones anteriores. El upsert limpia valores antiguos rechazados, incluso cuando el nuevo valor es NULL. Una excepción revierte la transacción y falla el job; el siguiente intento repite los pendientes. No crea proyectos ni publicaciones durante el reproceso.

El exportador conserva sus campos anteriores y añade `fechaPublicacion`, `descripcionFuente`, `resumenEvidencia`, `contenidoEstado` y `contenidoDesconocido`. `fechaAcuerdo` y `estadoTramitacion` usan el contrato municipal cuando existe.

## Validación

Las pruebas locales `db/test_project_semantics.py` y `db/test_project_semantics_postgres.py` cubren alias y casos ambiguos por contrato, más PostgreSQL 16 aislado: ingesta repetida, eliminación de campos, cambio de fuente, cambio de plantilla, fallo transaccional y recuperación, cardinalidad de proyectos e historial.

## Límites pendientes de #851

La versión 1 extrae hechos de campos del adaptador, no del texto completo de cada PDF. Un cambio de URL/documentación o de contenido del registro invalida el hash. Un PDF modificado bajo la misma URL sin cambio del registro necesita un monitor de hash documental para disparar este contrato; esta PR no implementa esa infraestructura. La siguiente revisión debe integrar ese disparador y parsers de documento con citas. La exportación aporta el estado de falta de descripción; la presentación específica de ese estado en la ficha web todavía requiere trabajo. Por esos motivos la PR referencia la issue y no la cierra.
