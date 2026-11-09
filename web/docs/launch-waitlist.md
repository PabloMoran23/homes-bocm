# Aviso de lanzamiento

Los bloques de proyecto, boletín (debajo del mapa de los resultados) y dashboard recogen
solicitudes para avisar cuando estén disponibles las funciones anunciadas.
No se muestra el formulario en la home ni en el buscador del boletín. No activa alertas ni envía correos todavía.

Antes de recoger correos en producción:

1. Aplicar `supabase/migrations/20261105120000_launch_waitlist.sql` desde la raíz del repositorio.
2. Configurar `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` y `LAUNCH_WAITLIST_KEY` en el servidor.

Las solicitudes se guardan en `public.homes_launch_waitlist`, con fecha y versión
del texto de autorización, sección de origen (`project`, `boletin`, `dashboard`)
y el identificador del proyecto cuando corresponde. No se guardan direcciones
consultadas en el boletín. Cada combinación de correo, sección y proyecto tiene
su propia solicitud; los duplicados no cambian la fecha original.
La tabla no permite acceso desde el navegador. El formulario solo confirma el
registro cuando la base de datos responde correctamente; si falta configuración o
la tabla, muestra un error y permite reintentar.

La clave `LAUNCH_WAITLIST_KEY` se guarda únicamente en el servidor; su hash SHA-256
se configura en `public.homes_launch_waitlist_config`. La función RPC solo permite
registrar solicitudes: no lee correos ni concede acceso general a la base de datos. Esta versión no envía avisos ni suscribe a
una newsletter. El envío del aviso de lanzamiento queda para cuando exista la función.

## Producción

El 5 de noviembre de 2026 se aplicó la migración en el proyecto de Supabase
`rjwcmbllrzqvsbgaajmp` y se configuró `LAUNCH_WAITLIST_KEY` en Vercel (Production).
La comprobación de inserción y duplicados se ejecutó sin conservar datos de prueba.
