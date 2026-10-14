# Política de entidades urbanísticas (H01)

La política `municipio/entity_policy.py` clasifica mediante estructura y evidencia.
`/catalog/` solo activa revisión: un expediente identificable con procedencia sigue
siendo elegible. Formularios, normativa, documentos, anuncios sin identidad,
categorías ajenas al urbanismo y casos ambiguos se conservan en las tablas y los
JSONL originales, pero no entran en actividad. Las licencias requieren fecha real
de concesión o acto/estado explícito; solicitudes, denegaciones, revocaciones y contradicciones
prevalecen incluso frente a una fecha positiva; una fecha de solicitud nunca se convierte
en concesión. No se emplean agentes ni modelos en la ingesta.

La lista `municipio/policies/entity_categories.json` se versiona en Git y su hash
forma parte de la versión efectiva. Cambiar reglas de código exige incrementar
`RULE_VERSION`. El hash de contenido excluye `_entity_policy` y
`_semantic_contract`, manteniendo ambos metadatos originales en raw.

## Integración y operación

1. La migración prepara config/cola/triggers/vistas con **control_active=false**;
   NO cambia las RPC ni activa filtros públicos. Mientras se prepara el histórico,
   las vistas conservan la lectura previa explícitamente. Si llega primero el
   código, `save_proyectos`/`save_licencias` hacen ese bootstrap idempotente antes
   de escribir: no dependen de que la cola ya exista. Un advisory lock serializa
   ese bootstrap; si llega primero la migración, los escritores antiguos siguen
   funcionando y sus cambios se encolan.
2. `python db/entity_reprocess.py` prepara la versión objetivo y clasifica en
   lotes. Un fallo deja la activación anterior intacta y devuelve código no cero.
   Reintentar el mismo comando retoma únicamente las tareas pendientes.
3. Con toda fila preparada y sin backlog, el comando toma un lock SHARE sobre
   ambas tablas (bloquea escritores, permite lecturas), comprueba de nuevo la
   completitud, actualiza snapshots activos y RPC de la allowlist y cambia el
   flag/version en **una sola transacción**. Una firma inesperada aborta esta
   transacción completa; no hay ventana de RPC vacías durante el rollout.
4. En actualizaciones de política, cada `_entity_policy` guarda el candidato y
   un snapshot anidado `active` de la versión anterior. Tareas `policy_change`
   conservan la actividad válida hasta el cambio atómico. Las tareas
   `source_change` sí ocultan únicamente la entidad modificada. No se añaden
   nuevas claves raw ajenas a `_entity_policy`, de modo que el hash H02 no cambia.
5. Si se integra H03, sus guardias deben permitir actualizaciones de metadatos
   sobre históricos inválidos; si no, el worker registra el fallo y conserva el
   rollout anterior hasta corregir y reintentar. Ejecutar el replay GIS antes de
   la última clasificación H01. Repetir H01 tras otros replay que cambien evidencia.
6. Los workflows refresh-web-data, refresh-municipios y sync-supabase ejecutan
   este comando automáticamente. Los exportadores tienen preflight obligatorio:
   si el control está inactivo o la versión actual aún no está activa, fallan con
   un mensaje explícito para ejecutar el worker y no publican legado como si
   estuviera controlado. Las RPC y artefactos desplegados previos siguen sirviendo
   durante la preparación. Después, regenerar/publicar por el flujo normal.

`homes.entity_policy_rollout` expone `control_active`, versión activa/objetivo,
pendientes y fallos. Una instalación preparada no se presenta como protegida.
No se ha ejecutado ninguna migración ni replay productivo durante este trabajo.

El worker bloquea primero la entidad y después su tarea, con SKIP LOCKED. Nunca
retira una tarea de una entidad bloqueada por otro escritor. Los fallos quedan
con contador, último error y fecha en `homes.entity_reprocess_queue`; el proceso
continúa con las otras filas, devuelve código no cero y permite reintentar.
`homes.entity_policy_health` muestra backlog y fallos. Con el control activo, ninguna fuente cambiada pendiente o con error entra en
actividad. La versión activa anterior solo se conserva para cambios de regla
hasta la activación atómica de la siguiente versión. Un pico de
entidades desconocidas produce `status=adapter_incident` y reason_code en el
informe `*.entities.json` del adaptador (mínimo 10; ratio >=25 %; aumento >15 pp).
No se abre ni se envía una incidencia externa automáticamente.

## Consumidores

Los exportadores municipales, Madrid, directorio, sitemap y programas/conteos
leen `homes.proyecto_actividad` / `homes.licencia_actividad`. Las RPC instaladas
se reescriben solo mediante una allowlist explícita de firmas en la migración:

- Ficha: get_proyecto_portal, get_proyecto_info_extra, get_sigma_ficha,
  get_sigma_clasificacion, get_ubicacion_ficha.
- Listas: list_proyectos_madrid, list_sigma_clasificacion,
  list_sigma_bocm_by_expediente, list_proyectos_bocm_madrid,
  list_proyectos_investigados, list_sigma_metrics, list_sigma_map_cards.
- Mapas/proximidad: map_cm_portal, map_sigma_geojson, map_ubicaciones_bbox,
  map_cm_municipios, map_cm_portal_municipio, map_cm_portal_view_100, boletin_area.
- KPIs: madrid_dashboard_stats, web_summary.

Se conservan firmas, permisos y filtros actuales; lecturas FROM/JOIN de proyecto
/licencia pasan a las vistas, con cast explícito al helper compuesto del mapa.
Una firma o patrón de lectura inesperado aborta la migración. Consultas
administrativas fuera de la allowlist y tablas originales siguen accesibles;
no deben reutilizarse como fuente de actividad. El buscador de direcciones
search_ubicaciones se mantiene porque consulta inmuebles, no actividad.

## Validación y límites

Pruebas deterministas y transaccionales en `municipio/test_entity_policy.py` y
`db/test_entity_reprocess.py`; CI levanta PostgreSQL 16. La prueba de integración
exige H01_TEST_DB_URL en localhost y crea/elimina su propia DB temporal.

`audit_entity_activity.py` prepara 200 candidatos elegibles sin mostrar decisión
ni reason_code del clasificador. El workflow conserva la muestra como artefacto.
Un revisor debe verificar cuáles están publicados y completar dos booleanos:
identifiable_activity y generic_form. `--labels` comprueba >=95 % de precisión y
cero formularios; exige al menos 200 etiquetas completas. Los recursos no están
en el denominador. Un validador de tipos no demuestra precisión semántica.

Pendiente de validación operativa: aplicar migración y reproceso en un entorno
controlado, regenerar los artefactos y realizar la muestra ciega de **200
resultados efectivamente publicados**. No se ha medido precisión productiva ni
se ha desplegado. Los campos originales sin suficiente identidad quedan
pendientes, incluso si una heurística anterior los había publicado; la política
prefiere abstenerse. El muestreo de candidatos requiere contrastar publicación
real antes de emplearlo como criterio de cierre.

La versión h01-v3 valida la fecha de concesión mediante el contrato temporal H05: fechas observadas futuras, inválidas o parciales no prueban por sí solas una concesión. Un estado o acto afirmativo independiente puede probarla sin inventar la fecha. El cambio de versión fuerza el replay de las clasificaciones anteriores.
