# Revisiones municipales y SLA de 15 días (H08)

Este cambio es una infraestructura candidata, **no acredita todavía el SLA real de las 674 fuentes**. No debe desplegarse como cumplimiento de H08. La issue debe seguir abierta hasta completar los contratos de los adaptadores, límites HTTP y medidas reales indicados abajo.

## Capacidad y ejecución

`refresh-municipios.yml` refresca hasta 20 municipios vencidos cada 4 horas, por la ruta legacy de la base: este draft **no sustituye ni activa** el refresco operativo. Mantener el legado no demuestra que cumpla 15 días: sigue siendo una carencia abierta de H08.

El dimensionamiento candidato contempla despachos a :17 de cada hora cuando exista evidencia y se apruebe una activación futura; ese cron aún **no está configurado**. Tres trabajos secuenciales por despacho, cada uno con timeout duro de 12 minutos y lease de 15 minutos. El runner reserva 50 minutos incluyendo instalación, descarga de artefacto y limpieza. Son 72 intentos por 24 horas rodantes y 14,4 horas/día de trabajo de fuentes si todos agotan el timeout (hasta 20 horas/día de runner con el límite de 50 minutos/despacho); el coste y la disponibilidad de minutos Actions requieren validación operativa. El cron de Actions puede retrasarse o saltarse; no constituye una garantía de disponibilidad.

674/15 = 44,934 revisiones completas/día; se necesitan 45 completadas más reintentos. 72 intentos deja 27 intentos diarios de margen sobre esa necesidad, sujeto a duración y fallos. Se encola a los 13 días desde la revisión completa para reservar dos días de margen sin cambiar el requisito de 15 días. Todas las fuentes usan vencimiento y slug determinista: no se excluyen las menos consultadas. No se usa p95 como criterio de cumplimiento: se publica la lista completa de `sla_violations`, máximo de edad y completados.

Se reservan 3 intentos por fuente y 12 por host principal en 24 horas rodantes. Son presupuestos de revisiones, **no límites de peticiones HTTP**. El censo actual tiene 674 entradas programadas y el mayor host principal agrupa 5; la simulación usa esos hosts y todas las cadencias de los manifests. Un host compartido por 674 fuentes supera su capacidad y la prueba exige que se reporte incumplimiento.

## Estado durable y recuperación

La migración `20261014160000_refresh_review_queue.sql` crea cola, historial de intentos y métricas en PostgreSQL, con RLS y sin permisos de usuario web. Debe aplicarse antes de activar el workflow. No se usa `last_ingest_at` para inferir revisiones. `last_complete` acredita revisión de fuentes habilitadas, `last_write` acredita éxito del paso de escritura. Una revisión completa con fallo posterior de DB mantiene su timestamp y su reintento pendiente. Los timestamps históricos de escritura no se convierten en revisiones: el arranque queda rojo hasta tener evidencia.

Un bloqueo transaccional de PostgreSQL serializa claims entre runners. El token del lease impide que un runner vencido publique: el hijo recibe slug/token, captura en un directorio temporal privado y después invoca `Queue.publish`. El mismo bloqueo transaccional que toman claims/reconcile protege la comprobación de token y lease, la escritura canónica y la actualización de completion. El reloj real de PostgreSQL se comprueba antes de publicar y después de preparar las escrituras, antes de confirmar: si el lease vence durante SQL se revierte toda la transacción. Una revocación previa impide entrar al publisher; un claim/reconcile concurrente espera al lock. No se renueva ningún lease robado.

`sync_municipio_output` acepta un manifest de staging y una conexión propiedad del publisher; `IngestSession` no confirma, cierra ni oculta errores cuando recibe esa conexión. Su historial de ingest y los upserts quedan en la misma transacción que la cola. El camino legacy conserva sus conexiones y commits propios. El estado sobrevive al runner; el timeout o muerte sin confirmación deja un trabajo recuperable al vencer el lease y conserva el intento para métricas/presupuestos. Reconciliar el manifest es idempotente y un cambio de configuración o versión del contrato invalida la revisión y vuelve a encolarla. Las publicaciones siguen usando los identificadores estables y transacciones del pipeline actual.

Los errores tienen backoff exponencial limitado a 24 horas y jitter determinista por fuente/intento. Cada intento fallido consume su presupuesto; no se borra de la cola. Las fuentes bloqueadas aparecen con su error y SLA. El reporte JSON se conserva 30 días como artefacto y las métricas durable 90 días; un crecimiento de backlog respecto al corte de hace 24 horas o un SLA incumplido falla el job.

## Contrato de revisión y preservación

Cada runner de fuente habilitada debe devolver `review_complete: true` solamente después de recorrer todas sus páginas/rangos y fuentes exigidas, sin errores capturados, truncamiento ni límites agotados. `status: ok`, filas escritas y cero filas no son pruebas suficientes. El dispatcher copia los outputs anteriores a staging privado y no hace sync cuando falta esa evidencia. El candidato llama al orquestador con `staging=True`: ese modo rechaza pasos que incluyan sync y, ante timeout de enriquecimiento/geocode, devuelve un error para la cola sin llamar `defer_manifest` ni borrar `last_ingest_at` por una conexión ajena. Los callers legacy mantienen por defecto su deferral previo. La prueba PostgreSQL ejecuta el orquestador real y los helpers reales de deferral redirigidos al schema aislado: tanto el token revocado como el actual con timeout conservan la marca de frescura canónica, no publican ni registran ingest; solo el token válido puede añadir el backoff en la cola.

Nunca reemplaza los outputs canónicos del checkout con el staging; timeout o muerte del hijo descartan esa captura. Un fallo durante sincronización o una expiración revierte los cambios canónicos junto con el historial y el checkpoint. Repetir la publicación con el mismo token confirmado es rechazado antes de escribir.

Los adaptadores existentes **no implementan de forma general este contrato** y varios capturan errores de HTTP devolviendo `ok`. Por eso este draft falla cerrado y produce incumplimientos visibles; aún no puede sustituir operativamente todo el refresco existente. No añadir la marca a todos los adaptadores sin pruebas de paginación y fuentes: eso ocultaría el problema.

## Validación y trabajo pendiente

Las pruebas usan el censo real, 45 días de reloj simulado, 3 slots/hora, trabajos de 12 minutos, todos los presupuestos y un fallo inicial por ciclo en el 10% de las fuentes. Exigen primera revisión y **cada intervalo de cada fuente** dentro de 15 días, tres ciclos completos y el máximo de 72 intentos rodantes. Resultado del censo actual: primera vuelta máxima 10,300 días; máximo intervalo individual 13,042 días; 2409 revisiones completas y 243 fallos en 45 días, máximo 72 intentos/24h. No equivalen a tiempos y éxito observados de red. También prueban reinicio, expiración de lease, token antiguo, repetición de completion, configuración nueva, fallo aislado, restauración del output, timeout y ausencia de evidencia de revisión. Las pruebas PostgreSQL locales verifican claims concurrentes, reanudación y fencing de publicación real: un worker que ya perdió su lease termina un staging válido y se rechaza sin filas canónicas ni historial; el token del nuevo worker permanece intacto. El nuevo worker confirma exactamente una publicación y su repetición no añade filas. Un lease que vence durante las escrituras revierte tanto las filas canónicas como el historial de `IngestSession`; SQLite es solo backend del resto de pruebas.

Pendiente para cerrar H08:

- Completar y comprobar el contrato exhaustivo en los 674 adaptadores/fuentes, incluyendo páginas, ventanas incrementales y cambios de registros previamente conocidos. No basta que un adapter solo añada IDs nuevos.
- Añadir límites reales de peticiones/concurrencia por **todos** los hosts consultados, incluido HTTP indirecto, y rate limits definidos por fuente. Los presupuestos por host principal de esta cola no cubren hosts secundarios.
- Persistir checkpoints de páginas/evidencia original entre runners para fuentes largas; aquí solo el trabajo/lease y resultados finales son durables. El timeout antes de sync obliga a repetir la revisión completa.
- Medir duración, tasa de éxito, completados/ciclo y minutos disponibles de Actions; demostrar el SLA real con todas las fuentes y gestionar bloqueos externos. Validar nuevos censos por encima de 675 entradas o fuentes con intervalos más cortos.
- Incorporar señales verificadas de novedad/demanda manteniendo reserva para fuentes menos consultadas. Aquí el orden es FIFO por vencimiento para todas.
- Integrar reconciliación semántica/geográfica de otros PRs con su propia cadencia; no ejecutar un replay global sin límite en cada despacho horario.

No se ha aplicado migración, consultado/escrito producción, desplegado ni ejecutado scrapes de fuentes reales.
