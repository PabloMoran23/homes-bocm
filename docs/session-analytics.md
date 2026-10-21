# Analítica de sesiones

La medición propia complementa las visitas agregadas de Vercel. Se activa por defecto en la web, sin aviso de aceptación, y recoge sesiones por pestaña, con 30 minutos de inactividad. No identifica personas ni enlaza visitas de días diferentes. El origen de entrada se conserva al navegar; después de caducar en la misma pestaña se marca como interno.

## Datos

Páginas sin query string ni fragmentos (las ubicaciones se agrupan), origen Google/Bing/directo/interno/otras webs, proyectos seleccionados, pestañas de fichas, filtros de estadísticas, zonas generales y número de resultados. Nunca se guarda texto libre de búsqueda, direcciones, coordenadas, URLs completas de documentos, IP ni grabaciones.

Se acumula tiempo mientras la pestaña está visible y ha habido actividad en el último minuto. El scroll es del documento principal, no de paneles con scroll propio. No demuestra lectura. El panel distingue una sola página y ausencia de interacción medida; no inventa una tasa de rebote comparable a otra plataforma.

## Acceso y seguridad

`/admin/analitica` usa la contraseña y cookie de administrador existentes. En producción pública solo se habilitan esa página y el login; los otros paneles siguen bloqueados. La página valida la cookie también en servidor. Las tablas tienen RLS y sin permisos para anon/authenticated. Las RPC requieren un secreto de servidor cuyo hash se guarda en un esquema privado. El navegador nunca recibe el secreto.

La recepción exige mismo origen, lista cerrada de eventos/propiedades, tamaño y timestamps válidos. Se deduplica por UUID. Un límite compartido en base de datos permite 30 lotes por minuto y origen de red, usando un HMAC rotatorio que expira a las dos horas. Se incluyen también administradores y bots que ejecutan JavaScript. El servidor marca cada evento con `traffic_type`: `admin`, `bot` o `unclassified`, usando la sesión de administrador y las señales de automatización; estas señales no identifican todos los bots. Más de 100 vistas en una sesión se marca como sospechoso; no garantiza separar personas y bots. Un usuario puede bloquear la medición por lo que los datos pueden no incluir todas las visitas.

## Configuración

1. Aplicar `supabase/migrations/20261012120000_session_analytics.sql` usando la conexión PostgreSQL de servidor.
2. Generar un secreto aleatorio de al menos 32 bytes. Registrar SHA-256 hexadecimal en `homes_analytics_private.config` y poner el valor original en `ANALYTICS_RPC_KEY` del servidor.
3. Configurar `NEXT_PUBLIC_SESSION_ANALYTICS=1`, `ADMIN_PANEL_PASSWORD` robusta y `CRON_SECRET` en Vercel Production. Nunca usar NEXT_PUBLIC para secretos.
4. Desplegar. Vercel ejecuta `/api/analytics/retention` diariamente a las 03:15 UTC con CRON_SECRET. Borra solo eventos de más de 90 días y límites caducados. La ingesta y los informes antiguos también aplican esa retención. El panel nuevo (`homes_analytics_dashboard`) no borra filas.

Desactivar `NEXT_PUBLIC_SESSION_ANALYTICS` y volver a desplegar detiene la recogida ; mantener la tarea de retención mientras existan datos. No hay backfill de visitas previas.

## Verificación

`node scripts/test-session-analytics.mjs`, `npx tsc --noEmit`, lint de ficheros cambiados y build público. Comprobar en DB que anon no puede leer la tabla, una RPC sin secreto falla, retries no duplican eventos y los informes mantienen el origen y el tiempo por página. En producción comprobar login privado, lote válido, rechazo de payloads no permitidos y limpieza autenticada. Las pruebas de DB se ejecutan en una transacción revertida para no contaminar el informe.

## Filtros del panel

`/admin/analitica` lee `homes_analytics_dashboard` (`20261020150000_analytics_dashboard.sql`). Hay que aplicar esa migración antes de que el panel tenga datos; hasta entonces muestra que falta. La función agrega en la base de datos, no devuelve eventos en bruto y no borra filas. Caduca a los 3 segundos.

La URL guarda el periodo (`24h`, `7d`, `30d`, `90d` o `custom` con `from`/`to`), el tipo (`all`, `human`, `bot`, `admin`), el origen y la sección. `human` son sesiones sin marca de bot ni de administrador: el valor guardado sigue siendo `unclassified`. Los enlaces antiguos `days=7|30|90` y `traffic=unclassified|interesting` se leen como ese periodo y como personas. La comparación usa el periodo inmediatamente anterior, de la misma duración. Por debajo de 48 horas la serie es horaria; si no, diaria. El aviso de bots ignora el filtro de tipo para no esconder un pico.

Abrir una ficha no cuenta como acción. El rebote aproximado es una sola página, sin acción y con menos de 10 segundos activos. No hay dispositivo en los eventos, y `/ubicacion` agrupa todas las direcciones.
