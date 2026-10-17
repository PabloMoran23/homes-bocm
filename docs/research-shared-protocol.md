# Investigación territorial: asuntos, documentos y seguimiento

El proceso clasifica e investiga cualquier entrada relevante para la región: actuación,
planeamiento, modificación normativa, documento, subasta, trámite o anuncio. El nombre histórico
`homes.proyecto` identifica la entrada de origen; **no obliga a interpretarla como obra/proyecto**.
No modifica ni sustituye la política de actividad urbanística existente ni sus contadores.

## Modelo persistente

- `homes.asunto`: identidad canónica UUID, clave estable, tipo, título, municipio, fuente y
  `padre_id` confirmado. Los asuntos raíz tienen padre null. La BD rechaza ciclos.
- `homes.asunto_relacion`: origen/destino, tipo (`pertenece_a`, `modifica`, `afecta_a`, `describe`,
  `vinculado_a`), certeza y evidencia. Una relación posible nunca cambia el padre confirmado.
- `homes.entrada_investigacion`: foto inmutable de la investigación de una entrada, tipo,
  asunto_id, estado, relato, fuentes/búsquedas, datos/hallazgos, vínculos pendientes y payload.
- `homes.entrada_investigacion_actual`: foto actual y señal explícita de revisión.
- `homes.entrada_investigacion_lease`: reservas compartidas del nuevo proceso.
- `homes.entrada_investigacion_resumen`: clasificación, asunto/padre, resultado y elegibilidad
  por cambios de fuente, para inspección/integraciones posteriores.

Identificar un plan y dos capítulos produce un asunto plan y dos asuntos documento cuyo
padre_id apunta al mismo UUID. Dos fuentes del mismo plan deben reutilizar su clave oficial;
no se fusiona por título parecido ni se atribuyen padres por proximidad. La clave determinista
no resuelve por sí sola identidades semánticas redactadas con claves distintas: el investigador
compara el catálogo y cita evidencia. Si existe un padre diferente confirmado, el guardado
rechaza el conflicto en lugar de sobrescribirlo.

## Fallback sin información y no repetición

`pendiente_identificar` conserva el motivo cuando no se logra vincular la entrada con un asunto.
`parcial` conserva un asunto identificable con lagunas. Ambos **quedan procesados y fuera de la
selección automática**, igual que `completa`. No se usan skip ni un retry_after de 24h.

Si no hay fuentes accesibles, `fuentes` puede estar vacío, pero son obligatorios búsquedas
intentadas con consulta/resultado y huecos; si no hay asunto, también razon_pendiente. No se
inventan citas para satisfacer el esquema. No se permite una investigación completa sin fuentes.

Solo se reabre si cambia el contenido del registro fuente (fingerprint de su JSON, excluyendo
updated_at) o por una petición explícita:

```bash
python3 db/research_asunto.py review --project ID
```

Esto evita ciclos automáticos de búsquedas infructuosas sin borrar la evidencia de lo intentado.
Una investigación antigua en las tablas de proyectos no excluye la primera clasificación
territorial. Las fotos previas de ambos sistemas permanecen intactas.

## Adopción en Cursor

1. Aplicar **la migración aditiva** `20261017140000_regional_research.sql`, que es autónoma
   respecto de `20261017120000_research_leases.sql`. No hace falta desplegar el trigger antiguo
   que bloquea el escritor de `proyecto_investigacion`. La nueva migración crea tablas/vistas
   separadas y no altera el guardado antiguo ni la UI. Aplicarla una sola vez con el procedimiento
   habitual, con `SUPABASE_DB_URL` ya exportada:
   ```bash
   psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20261017140000_regional_research.sql
   ```
2. El usuario copia **TODO** `.cursor/prompts/investigar-proyecto.md` a Instructions de la
   automatización activa, con el checkout actualizado y psycopg2-binary disponible. El YAML
   del repo no actualiza la UI. No se cambia la UI desde esta implementación.
3. El nuevo contrato usa exclusivamente `research_asunto.py claim/context/renew/save` y
   produce el JSON territorial. Los clientes antiguos pueden seguir creando fichas antiguas;
   no participan en las nuevas reservas y no están cubiertos por su exclusión de trabajo.

Selección: primero fichas visitadas por sesiones humanas del filtro `interesting` existente,
excluyendo sesiones bot/admin completas; después viviendas/superficie/updated_at/id. Se usa
el historial retenido, sin nueva ventana ni mínimo inventado. Las rutas se decodifican y se
vinculan por alias exactos inequívocos (incluido BOCM y SIGMA), sin títulos aproximados.

```bash
python3 db/research_asunto.py claim --owner "cursor:UUID"
python3 db/research_asunto.py context --project "$ID"
python3 db/research_asunto.py renew --owner "$OWNER" --project "$ID" --token "$TOKEN"
python3 db/research_asunto.py save --file resultado.json --request-id "$REQUEST_ID" --source-hash "$SOURCE_HASH" --owner "$OWNER" --token "$TOKEN"
```

Conserva el source_hash del contexto; el guardado rechaza una fuente cambiada durante la investigación.
TTL por defecto 600s; renovar cada 120s. Al vencer se puede recuperar con token nuevo. Guardado
normal requiere reserva viva y valida otra vez su vencimiento al finalizar. Un request_id y JSON
idénticos devuelven el mismo id; cambiar el contenido de un reintento falla. Las identidades,
padres, relaciones, foto y puntero actual se escriben en una transacción. Un error revierte todo.
Los padres y relaciones deben incluir su URL/extracto; los desconocidos se guardan como vínculos
pendientes, nunca como un padre ficticio. Se conserva la calidad de relato y evidencia del contrato.

El helper Python admite `unleased_test=True` **solo para pruebas expresamente autorizadas**;
lo deja registrado como execution_mode=unleased_test. El CLI de Cursor no ofrece esa omisión.
No aporta exclusión frente a clientes antiguos. El ejecutor, cuota del 70%, configuración,
pruebas de supervisor y logs se mantienen exclusivamente en local, fuera de esta PR.

## Verificación

```bash
TEST_REGIONAL_DB_URL=postgresql://.../base_descartable python3 -m unittest discover -s db -p 'test_regional_research_postgres.py' -v
```

13 pruebas PostgreSQL: padres/IDs reutilizados, ciclos y conflicto de padre con rollback,
idempotencia, reservas/fencing/concurrencia, relaciones posibles, reapertura por cambios/revisión
rechazo de cambios de fuente durante la búsqueda y fallback sin información/fuentes que no se vuelve a seleccionar. La CI no importa código local.
**La suite borra el schema homes y la tabla de analítica de su base de pruebas; usar solo una base desechable.**

Los cambios de UI pública para presentar este nuevo historial no forman parte de esta entrega:
la clasificación ya está persistida y consultable en Supabase; no se afirma que la ficha web
antigua consuma automáticamente las nuevas tablas.
