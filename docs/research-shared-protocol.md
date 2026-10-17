# Investigación compartida: mismas tablas, clasificación y asuntos

El prompt de Cursor parte del texto proporcionado por el usuario. Los apartados **Investigar,
Resumen, Datos y Hallazgos se conservan literalmente** (salvo espacios del pegado). Solo se
sustituyen la selección por reserva y el guardado sin validación, y se añaden campos y reglas
para identificar planes, normas, documentos, subastas y casos sin información.

## Un único historial activo

- `homes.proyecto_investigacion`: investigación, tipo de entrada, estado, asunto_id, motivo,
  fuentes/búsquedas, vínculos pendientes, payload original y metadatos de idempotencia.
- `homes.proyecto_dato_extra`: cada dato, con los seis bloques y campos habituales.
- `homes.proyecto_hallazgo`: cada hallazgo, con los campos habituales.
- `homes.asunto` y `homes.asunto_relacion`: identidades UUID reutilizadas, padre confirmado y
  otros vínculos con evidencia. Los padres desconocidos permanecen null, sin inventarlos.
- `homes.proyecto_investigacion_actual`, `_lease` y `_resumen`: puntero actual, reserva y vista
  de seguimiento, sin otro historial de investigaciones.

El JSON conserva proyecto_id, estado, resumen, huecos, datos y hallazgos. Se añaden tipo_entrada,
asunto_ref/asuntos/relaciones, fuentes, busquedas_intentadas, razon_pendiente y vinculos_pendientes.
Las refs son locales al JSON; el helper las resuelve a IDs. `proyecto_id` sigue siendo el ID de
la entrada de origen, aunque corresponda a un plano, norma o subasta.

El guardado mantiene su punto de entrada:

```bash
python3 db/save_proyecto_info_extra.py --file resultado.json --request-id "$REQUEST_ID" --source-hash "$SOURCE_HASH" --owner "$OWNER" --token "$TOKEN"
```

Con REQUEST_ID/campos nuevos delega en el guardado ampliado y escribe las mismas tres tablas,
además de los asuntos/relaciones, en una transacción. Sin esos argumentos conserva la ruta
histórica para clientes anteriores. Mismo request_id y payload devuelve el mismo id; un payload
distinto con el mismo request_id falla. Source hash del contexto y reserva se validan al guardar.

## Fallback y no repetición

`estado` admite completa, parcial y pendiente_identificar. Un caso sin identidad suficiente
conserva motivo, huecos y búsquedas intentadas; si no hay fuentes accesibles puede tener
fuentes/datos vacíos, sin citas inventadas. Los tres estados quedan procesados y no se vuelven
a seleccionar por estar pendientes. Solo cambian por nueva fuente o revisión solicitada:

```bash
python3 db/research_asunto.py review --project ID
```

Los selectores antiguos que excluyen cualquier fila de proyecto_investigacion también ven
los resultados consolidados, incluidos los pendientes, y no los vuelven a seleccionar.
La clasificación territorial completa requiere el contrato y helpers actualizados.

## Reserva y uso en Cursor

```bash
python3 db/research_asunto.py claim --owner "cursor:UUID" --ttl 600
python3 db/research_asunto.py context --project "$ID"
python3 db/research_asunto.py renew --project "$ID" --owner "$OWNER" --token "$TOKEN" --ttl 600
```

Claim devuelve id/owner/token/source_hash; conservar también source_hash del contexto.
Selección atómica con bloqueo de proyecto y revalidación en snapshot fresco. Prioridad para
fichas visitadas en sesiones humanas del filtro existing `interesting`, sin bots/admin; después
viviendas, superficie, actualización e id. Sin nueva ventana ni umbral de visitas inventado.
TTL 600s por defecto, renovar cada 120s. Ante abandono, `release` con id/owner/token. Una reserva
vencida/reemplazada no puede guardar. Se verifica otra vez al finalizar la transacción.

El usuario copia TODO `.cursor/prompts/investigar-proyecto.md` a Instructions de la UI activa,
con el checkout y secretos de conexión actualizados. Pegar el MD no instala helpers ni cambia
la rama main del checkout. No se modifica la UI desde esta implementación. El ejecutor Luna,
capacidad/cuota del 70% y scripts de prueba siguen exclusivamente en local, fuera de Git/PR.

## Migraciones y preservación

Se aplicó `20261017140000_regional_research.sql` para la prueba territorial inicial; la migración
siguiente `20261017160000_unify_regional_investigations.sql` consolida sus resultados en las
tablas habituales. Es transaccional y verifica conteos y payloads antes de retirar la tabla
experimental del uso activo. Los nuevos IDs comunes mantienen el id experimental de origen en
`entrada_legacy_id`; asunto_id, padre_id, fuentes, fechas y request_id se preservan. Las relaciones
y punteros se actualizan a los IDs comunes. Se conserva una copia privada de recuperación,
`entrada_investigacion_archivo_20261017`, bloqueada para escritura y excluida de todos los helpers.

Los bloques experimentales se traducen a los seis bloques existentes; el dato original queda
en raw_json y en el payload de la investigación. Datos basados solo en contexto/búsqueda, sin
fuente publicable, quedan publicable=false. No se convierten en cifras oficiales ni KPIs.
Los metadatos internos/raw_json no se exponen a anon/authenticated por permisos heredados.

Las investigaciones antiguas mantienen IDs y contenido. Se inicia su seguimiento de cambios
con un fingerprint tomado al consolidar; no afirma que la investigación histórica leyera esa
misma versión de la fuente. El trigger de reserva antiguo se adapta si ya estaba instalado;
la consolidación no lo instala donde no existía, para no romper al escritor activo de Cursor.

La RPC web sigue devolviendo datos/hallazgos con su forma habitual y añade clasificación segura.
El lector admite pendiente_identificar y muestra su motivo; en documentos/normas la sección
programa se titula «Contenido y condiciones». Estos cambios de web se distribuyen con la PR,
no se afirma que estén desplegados en producción antes de integrarla.

## Pruebas

```bash
TEST_REGIONAL_DB_URL=postgresql://.../base_descartable python3 -m unittest discover -s db -p 'test_regional_research_postgres.py' -v
node web/scripts/test-proyecto-info-extra.mjs
```

Se comprueban migración con datos previos y guard activo, payload/IDs/relaciones, normalización
conservadora de hechos, privacidad, reintentos, fachada de guardado histórica, reservas/ciclos,
fallback sin repetición y conservación textual del núcleo del prompt del usuario. La suite web
prueba compatibilidad con estados anteriores y renderizado de pendientes/contenido territorial.
**La suite PostgreSQL borra homes y analítica en su base de pruebas: usar solo una base desechable.**
