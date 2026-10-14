# Política de entidades urbanísticas (H01)

La política `municipio/entity_policy.py` clasifica mediante estructura y evidencia.
`/catalog/` solo activa revisión: un expediente identificable con procedencia sigue
siendo elegible. Formularios, normativa, documentos, anuncios sin identidad,
categorías ajenas al urbanismo y casos ambiguos se conservan en las tablas y los
JSONL originales, pero no entran en actividad. Las licencias requieren fecha real
de concesión o acto/estado explícito; una fecha de solicitud nunca se convierte
en concesión. No se emplean agentes ni modelos en la ingesta.

La lista `municipio/policies/entity_categories.json` se versiona en Git y su hash
forma parte de la versión efectiva. Cambiar reglas de código exige incrementar
`RULE_VERSION`. El hash de contenido excluye `_entity_policy` y
`_semantic_contract`, manteniendo ambos metadatos originales en raw.

## Integración y operación

1. Aplicar `20261014235900_entity_activity_policy.sql` mediante el proceso normal
   de migraciones. No se ha ejecutado en producción durante este trabajo.
2. Si se integra H03, sanear primero sus outliers geográficos históricos: los
   CHECK NOT VALID de H03 también se exigen al actualizar metadatos de esos rows.
3. Ejecutar `python db/entity_reprocess.py` antes de publicar. Altas, cambios e
   histórico comparten la misma cola y política. Una versión nueva encola solo
   filas cuya versión es distinta. Altas/cambios por SQL externo se encolan por
   trigger; `save_proyectos` y `save_licencias` procesan sus filas en la misma
   transacción. Cambios de programas, métricas o GIS derivados no invalidan la
   clasificación si no cambian evidencia usada por esta política.
4. Ejecutar de nuevo tras otros replay que cambien evidencia (semántica H02,
   fuentes originales) y antes de exportar. Los workflows refresh-web-data,
   refresh-municipios y sync-supabase ejecutan el worker automáticamente.
5. Regenerar/publicar los artefactos web por el flujo existente: la migración no
   modifica JSON estáticos ya desplegados. No publicar hasta vaciar la cola.

El worker bloquea primero la entidad y después su tarea, con SKIP LOCKED. Nunca
retira una tarea de una entidad bloqueada por otro escritor. Los fallos quedan
con contador, último error y fecha en `homes.entity_reprocess_queue`; el proceso
continúa con las otras filas, devuelve código no cero y permite reintentar.
`homes.entity_policy_health` muestra backlog y fallos. Ninguna entidad pendiente,
con error o política obsoleta entra en las vistas de actividad. Un pico de
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
