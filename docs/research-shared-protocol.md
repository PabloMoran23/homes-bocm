# Investigación compartida: Supabase y Cursor

Esta entrega versiona únicamente el protocolo de selección/reserva/guardado que comparten
Cursor y los investigadores externos. El ejecutor Luna, su configuración, vigilancia de cuota,
pruebas y documentación de ejecución se mantienen exclusivamente en local, fuera del repo.
La PR y su CI no necesitan ningún archivo del ejecutor para aplicar o probar este protocolo.

## Adopción por Cursor

1. Pausar la automatización activa de Cursor y dejar terminar las ejecuciones antiguas.
2. Actualizar su checkout a esta versión. Con el procedimiento habitual de despliegue aplicar
   una sola vez `supabase/migrations/20261017120000_research_leases.sql`. Requiere las tablas
   de investigación y `public.homes_analytics_events` existentes. Por ejemplo, desde el repo,
   con `SUPABASE_DB_URL` ya exportada:
   ```bash
   psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20261017120000_research_leases.sql
   ```
   La migración es transaccional, conserva la historia y rechaza **nuevas investigaciones sin
   reserva**, también si un cliente antiguo intenta insertarlas directamente.
3. **El usuario copia todo `.cursor/prompts/investigar-proyecto.md` en Instructions de la UI
   activa de Cursor.** La UI no lee ese archivo ni el YAML local automáticamente. Debe contener
   `research_lease.py claim`, renovación cada 120s y guardado con owner/token obligatorio.
   Mantener la instalación de `psycopg2-binary` y los secretos de conexión de Cursor.
4. Reactivar Cursor después de adoptar el contrato. Ningún cambio de esta PR modifica su UI.
   Mientras la copia activa no use reservas todavía puede duplicar trabajo, aunque el trigger
   impida el segundo guardado. No se garantiza exclusión del trabajo de clientes no adoptados.

No se aplica automáticamente la migración ni se inicia ninguna investigación al integrar
estos archivos. El ejecutor local se activa separadamente, después de esta adopción.

## Selección, prioridad humana y unidad de trabajo

`db/research_lease.py claim --owner <owner-unico> --ttl 600` reserva atómicamente un
`homes.proyecto.id`, bloqueando proyecto con `FOR UPDATE SKIP LOCKED` y volviendo a comprobar
la elegibilidad en un snapshot fresco antes de escribir la reserva.

Primero van fichas visitadas en sesiones del filtro existente **`interesting`** de
`20261013190000_analytics_session_filters.sql`: sin ninguna marca bot/admin ni ruta `/admin%`
en toda la sesión, 1–100 pageviews y multipágina, acción significativa o ≥10s activos sumando
los máximos por página. Es la heurística humana de nuestra analítica, no identidad personal
verificada ni simplemente tráfico sin marca de bot. Si cambia el filtro existente hay que
actualizar también la vista privada `homes.research_human_project_visits`.

Se usa todo el historial que siga retenido en la tabla, sin introducir nueva ventana o
mínimo de visitas. La analítica ya limpia a 90 días; el selector no limpia ni fija otro plazo.
No ordena por volumen de tráfico. Dentro de ambas prioridades mantiene viviendas, superficie,
actualización e id como desempate. Cualquier investigación previa, incluida parcial, excluye
al proyecto, y una reserva viva o un descarte temporal también lo excluyen.

Las visitas `page_view` y `ficha_proyecto_ver` se vinculan por la URL `/proyecto/<id>` decodificada
una vez, solo con identificadores/alias exactos e inequívocos: id, BOCM, expediente o slug SIGMA.
Rutas inválidas, desconocidas o ambiguas no aportan prioridad; no se usan títulos parecidos
ni clicks del mapa como si fueran visitas a una ficha.

El JSON de reserva contiene la fila completa. `research_lease.py context --owner <owner>
--project <id>` lee trámites, documentos, publicaciones BOCM y métricas PDF existentes.
El contrato obliga a investigar la actuación real, distinguiéndola de documentos genéricos.
`skip` con owner/token y motivo aparta 24h una ordenanza, catálogo o ficha vacía sin inventar
una investigación. No se fusionan ids distintos por semejanza: la reserva evita duplicados
por proyecto_id, **no resuelve la identidad semántica entre dos ids de una misma actuación**.

## Renovación, fencing y guardado

Cada ejecución usa owner único y cada reserva token UUID nuevo. El reloj de PostgreSQL decide
el vencimiento. `renew` y `release` exigen id/owner/token; TTL entre 60 y 3600 segundos (600
por defecto). Cursor renueva al menos cada 120s y se detiene si falla. Ante caída, la reserva
vence y puede recuperarse con otro token. El propietario antiguo no puede renovar, liberar
ni guardar tras el relevo. Todos los caminos bloquean primero proyecto, después lease.

El guardado obligatorio es:

```bash
python3 db/save_proyecto_info_extra.py --file resultado.json --owner "$OWNER" --token "$TOKEN"
```

Valida reserva viva, relato y fuentes básicas; inserta `proyecto_investigacion`,
`proyecto_dato_extra`, `proyecto_hallazgo` y registra id/hash en una sola transacción.
Vuelve a verificar vencimiento antes del commit. Un trigger rechaza incluso el INSERT
antiguo sin reserva. Repetir el mismo JSON con el mismo owner/token devuelve el mismo id;
cambiar el contenido del reintento falla. Un error revierte las tres tablas. Esta ruta crea
la primera investigación: no edita ni refresca fichas existentes.

Se conserva el contrato de relato extenso, cronología, citas verificables, fuentes oficiales
primero y separación de cifras vigentes, máximos, estimaciones e históricos anulados. Las
fechas desconocidas permanecen null. Las cifras anuladas no deben destacarse como KPI vigente.

## Pruebas compartidas, sin ejecutor ni inferencia

```bash
TEST_RESEARCH_DB_URL=postgresql://.../base_descartable python3 -m unittest discover -s db -p 'test_research_leases_postgres.py' -v
```

La suite tiene 12 pruebas PostgreSQL: reservas concurrentes Cursor/Luna, caducidad y relevo,
renovación, guardado/reintentos concurrentes idempotentes, rollback de las tres tablas incluso
si vence durante el guardado, rechazo de clientes antiguos y prioridad humana/rutas/alias.
La CI `Shared research leases` ejecuta esta suite en PostgreSQL 16 aislado sin código local.

**La suite borra el schema `homes` y la tabla de analítica en su base de pruebas.** Usar
exclusivamente una base desechable, nunca Supabase de producción.
