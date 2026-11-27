# Seguimiento de proyecto y avisos anteriores

En la ficha (`/proyecto/[id]`) la persona puede dejar su correo. El mismo formulario aparece en la cabecera, al inicio de los documentos oficiales y al pie. En móvil, una barra fija abre el formulario. Solo pide el correo. Después del alta, y en la misma confirmación, puede indicar por qué lo sigue. Esa respuesta es opcional.

Si el expediente sigue en tramitación, el título es «Sigue este proyecto» y el aviso es de un cambio de fase o de documentación nueva. Si el expediente está cerrado (archivado, caducado, anulado, firme o con aprobación definitiva) o es el plan general, el título es «Avísame de lo nuevo en [barrio, distrito o municipio]» y el aviso es de un proyecto nuevo o de un cambio de planeamiento en ese lugar. Una modificación del plan general que sigue en tramitación se trata como proyecto. El plan general nombra el municipio; un expediente cerrado nombra el barrio o el distrito, y si no hay nombre de lugar usa el municipio.

El boletín y el dashboard conservan su formulario anterior. No envían correos.

## Datos

Se reutiliza `public.homes_launch_waitlist`. La clave sigue siendo correo + sección + proyecto, así que un mismo correo no crea dos altas del mismo proyecto y no reescribe la fila original.

Columnas nuevas, todas opcionales para no tocar las altas ya guardadas:

| Columna | Contenido |
| --- | --- |
| `context_key` | Id del proyecto (ya existía) |
| `municipio` | Municipio de la ficha, si se conoce |
| `posicion` | `cabecera`, `documentos`, `pie` o `barra` |
| `created_at` | Fecha del alta (ya existía; no cambia en un duplicado) |
| `referrer` | Web de origen, sin consulta ni fragmento. Vacío si entra directa o desde la propia web |
| `utm` | `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` si venían en la ficha |
| `segmento` | Respuesta opcional. Solo se rellena si aún estaba vacío |
| `aviso` | `proyecto` si el expediente sigue en tramitación; `zona` si está cerrado o es el plan general |
| `ambito` | Barrio, distrito o municipio que nombra el formulario. No cambia en un duplicado |

La versión del texto en altas nuevas de ficha es `seguir-proyecto-v1`. Las filas anteriores conservan `launch-notice-…`.

## Migración

Aplicar `supabase/migrations/20261127120000_seguir_proyecto.sql` **antes** de desplegar el código que envía los campos nuevos. Hasta entonces el alta responde error y no confirma el correo. La migración no borra filas ni envía correos.

`LAUNCH_WAITLIST_KEY` sigue igual: solo autoriza el registro. El navegador no lee la tabla.

## Analítica

Los eventos pasan por `/api/analytics` y el mismo marcado de bots (`traffic_type`: `admin`, `bot` o `unclassified`):

- `seguir_visto` — `posicion`, una vez por sesión y posición, cuando el formulario entra en pantalla
- `seguir_clic` — `posicion`
- `seguir_alta` — `posicion` y `proyecto`
- `seguir_segmento` — `valor`

Hay que aplicar la misma migración para que la tabla de analítica acepte esos nombres.

## Informe diario

En este repositorio no hay un informe diario de producto. La tarea programada de analítica solo borra eventos de más de 90 días (`/api/analytics/retention`). El panel `/admin/analitica` no es ese informe. La sección «Seguir proyecto» (vistas por posición, altas, tasas, ficha, municipio, segmento y top 10) queda para el informe operativo externo. No se añade aquí otro sistema ni Search Console.

## Privacidad

El formulario enlaza a `/privacidad`. En el repositorio no hay una política de privacidad, y la que pudiera publicarse fuera de aquí no está redactada para este uso (avisos de un proyecto o de novedades en un barrio o municipio). Hay que escribirla antes de recoger correos con el texto nuevo. No se ha redactado en este cambio.

## Comprobación

`node scripts/test-launch-waitlist.mjs` y `node scripts/test-seguir-proyecto.mjs`.
