# Web · Homes Urbanismo (Madrid)

Portal Next.js: mapa unificado (SIGMA + licencias + BOCM), boletín por zona, fichas y
estadísticas. Datos estáticos en `public/data/`; Supabase para RPC dinámicos.

## Requisitos

- Node 20+
- Para regenerar datos: CSV/artefactos en `poc-bocm/output/` (ver README raíz).
- `web/.env.local` con `NEXT_PUBLIC_SUPABASE_*` (copiar de `.env.local.example`).

## Comandos

```bash
npm install
npm run dev:public      # MVP Madrid (como producción)
npm run dev             # edición full (todas las rutas de desarrollo)
npm run build-data      # regenera public/data (scope según BUILD_DATA_SCOPE)
npm run build:public    # build producción con datos madrid-public
npm run verify:production   # comprueba datos + build public
```

En Vercel no se ejecuta `build-data` (`SKIP_BUILD_DATA=1`); los JSON deben estar en git.
Ver `../docs/production-web.md`.

## Rutas (edición `public`)

| Ruta | Descripción |
|------|-------------|
| `/` | Landing |
| `/explore` | Mapa unificado Madrid |
| `/boletin` | Qué ocurre en tu zona |
| `/madrid/estadisticas` | Panel SIGMA + licencias |
| `/proyecto/[id]`, `/ubicacion/[ndp]` | Fichas |

Rutas `/madrid/bocm`, `/planes`, etc. están en desarrollo (redirigen a `/en-desarrollo`).

## Stack

Next.js 16 (App Router), Tailwind CSS v4, react-leaflet, Chart.js, Supabase.

## Autocompletado de direcciones

La landing y `/boletin` comparten un buscador nacional sobre el callejero oficial de
CartoCiudad (IGN). No requiere cuenta, token ni SDK de mapas. Las sugerencias pasan
por `/api/geocode-address/suggestions`; al elegir una se resuelven las coordenadas
con `/api/geocode-address/resolve`. El boletín recibe las coordenadas directamente.

El componente espera 350 ms tras escribir y cancela peticiones obsoletas. Cuando
falta el tipo de vía se consulta también la variante con «calle» y se ordenan los
resultados por los términos escritos, incluido el número de portal. Las calles
sin número se identifican como «Calle completa» para no sugerir precisión de portal.

El autocompletado es nacional; el análisis del boletín sigue limitado a Madrid
capital. Para otros municipios se muestra explícitamente la cobertura disponible.

Validación: `npm run test:address`. Para comprobar las consultas reales contra el
IGN: `node scripts/test-address-autocomplete.mjs --live` (requiere red).

## Fondo de la landing

La cabecera sirve `public/maps/landing-madrid.webp` (34 KiB) como imagen decorativa
local de carga inmediata. No monta MapLibre ni descarga teselas para ese fondo.
Para regenerarla: `node scripts/build-landing-background.mjs`. Solo el generador
necesita red (OpenFreeMap); conserva los créditos cartográficos en la landing.

## Miniaturas del directorio de provincias

`/proyectos` sirve imágenes WebP locales de `public/maps/provinces/`; no inicializa
MapLibre ni descarga teselas en el navegador para las tarjetas. Los mapas de las
páginas de provincia y municipio siguen siendo interactivos.

Las imágenes encuadran el contorno provincial del IGN y no muestran puntos de proyectos.
Los límites simplificados se guardan en `data/province-boundaries.json`.

Al añadir provincias a `data/project-directory.json`, regenerar y guardar las
miniaturas junto con los datos:

```bash
npm run build:province-boundaries # opcional: actualiza límites desde el IGN
npm run build:province-previews  # requiere red; usa teselas de OpenFreeMap
npm run check:province-previews # verifica cobertura y dimensiones sin red
```

La generación se ejecuta explícitamente, no durante una visita ni en el build de
Vercel. Mantener los créditos de OpenStreetMap, OpenMapTiles e IGN del directorio.


### Tu zona: proyectos y contexto

`/boletin` ofrece visión de conjunto, proyectos y planes, cambios fechados y
licencias. Los ámbitos se consultan por su geometría real, incluidos los planes
anteriores al periodo seleccionado y el planeamiento de alcance general.
`/api/boletin-area/context` combina el catálogo local con la consulta municipal;
las geometrías se simplifican solo después de calcular la proximidad.
`/api/boletin-area/project` reutiliza los cargadores y paneles de la ficha de
proyecto para mostrar investigación, datos, cronología y documentos oficiales.

Los hitos de investigación usan fechas explícitas del acontecimiento, distinguen
aprobación de publicación y actualizan fases antiguas del catálogo. La fecha de
revisión de una ficha no se presenta como un cambio del proyecto; una aprobación
no confirma obras en ejecución. La cobertura de esta consulta sigue siendo Madrid
capital. No requiere migraciones de base de datos.

El resumen inicial prioriza la última aprobación, las propuestas con novedades y
las licencias por tipo de actuación. `/api/boletin-area/monthly` elige un periodo
móvil común: 1, 3, 6 o 12 meses y, si lo permite el filtro, 24 o 36. Selecciona el
tramo más corto que reúna 20 registros próximos o llega al límite de la consulta.
Nunca incorpora fechas anteriores al filtro ni futuras y no desplaza el periodo
hacia atrás por retrasos de la fuente. Mantiene la misma convención temporal de la
consulta (meses de 30 días), mostrando las fechas exactas de inicio y fin.

Cuenta por fecha de concesión y distancia real en los archivos municipales
completos disponibles (no la muestra de 40 eventos de la cronología). Carga los
años necesarios según el índice publicado y renueva la caché cuando cambia su
versión. La fecha más reciente del archivo se muestra si lleva retraso. Incluye
declaraciones responsables identificadas según la clasificación compartida de
actuaciones. Las categorías usan siempre el mismo intervalo para ser comparables.

Validación: `npm run test:area` y `npx tsc --noEmit`.

### Contrato de alcance de las estadísticas

`summary.json.statisticsScope` (versión 1) se genera en ambos exportadores en cada
build: no se mantiene a mano. Declara ámbito, fuentes y territorios incluidos,
periodo observado, fecha de comprobación y denominador de todos los anuncios
publicados. `full` significa conjunto de fuentes incluidas, con cobertura nacional
**parcial**; no prueba exhaustividad ni homogeneidad territorial o temporal.
`madrid-public` nunca es elegible para el panel España.

`npm run build-data` y `npm run build` validan el contrato, incluso cuando
`SKIP_BUILD_DATA=1`. Un manifest ausente, un ámbito desconocido o una divergencia
de los totales aborta el build con `statistics-scope`. Después de actualizar código
que introduce este contrato, hay que regenerar los datos con el exportador habitual
antes de publicar; los snapshots antiguos sin manifest se rechazan. La página
valida de nuevo cada lectura, registra una advertencia y muestra indisponibilidad
nacional ante datos incompatibles. No sustituye esa indisponibilidad con cifras
regionales ni infiere cobertura completa a partir de la presencia de registros.

Pruebas del contrato, adaptador y HTML: `node scripts/test-statistics-scope.mjs`.
Comprobación del artefacto publicado (HTTP/JSON/contrato fallan con salida no cero):
`node scripts/assert-statistics-scope.mjs https://TU_HOST/data/summary.json`.
El intervalo del manifest describe años observados, no años cerrados ni una prueba
de completitud de la ingesta. Las fuentes originales se conservan; cambiar fuentes
o reglas exige regenerar el resumen por el mismo proceso.

El prebuild convierte también un snapshot cacheado anterior al contrato mediante `build-statistics-scope.mjs`, usando la misma función de exportación. Conserva fechas y conteos, valida el resultado y publica el JSON atómicamente; no repara manifiestos contradictorios ni deduce alcance de un nombre de archivo. La transición es idempotente y no requiere acceso a la base de datos.

### Tu zona fuera de Madrid capital

La búsqueda de direcciones funciona en España. Para los municipios del directorio o del catálogo municipal actualizado,
`/api/boletin-area/national` devuelve dos alcances explícitos: proyectos próximos
con geometría y procedencia identificadas, y contexto del conjunto del municipio.
La resolución exige coincidencia del nombre municipal y coherencia geográfica;
no asigna automáticamente el municipio más próximo ni confunde homónimos.

Las consultas públicas de mapa proporcionan geometrías, metadatos y fechas. Se
consultan por separado el entorno de la dirección, el municipio y el periodo
reciente. La selección está acotada; el enlace municipal permite continuar en el
directorio. Los centroides municipales y las ubicaciones aproximadas no se usan
para calcular proximidad. Los adjuntos identificados como archivos no ocupan
una tarjeta de proyecto independiente. Las fichas mantienen sus enlaces canónicos.

Si faltan novedades fechadas, se muestran antecedentes y registros sin fecha,
señalando ese alcance. Los años o las revisiones del catálogo no se convierten en
hitos recientes. Si falla la actualización, se identifica el catálogo de respaldo.
Una dirección sin municipio cubierto muestra la limitación y alternativas próximas,
sin afirmar ausencia de actividad. Las licencias detalladas siguen disponibles en
Madrid capital; fuera de ella no se publican contadores sin cobertura acreditada.

Pruebas: `npm run test:area` incluye resolución municipal, homónimos, geolocalización,
fechas, fallback y búsqueda nacional. No requiere migraciones de base de datos.

### Búsqueda y página de resultados de Tu zona

`/boletin` presenta el buscador; `/boletin/resultados` carga la consulta sin repetir
el formulario ni la introducción. La URL conserva dirección, coordenadas, municipio,
radio y periodo. El breadcrumb vuelve a `/boletin?edit=1` conservando la consulta
sin ejecutarla otra vez. Los enlaces antiguos con parámetros redirigen a resultados;
la landing y los enlaces de edificios apuntan directamente a la nueva ruta. Las
páginas de resultados no se indexan. La navegación cancela las consultas pendientes
y los callbacks de redimensionado del mapa al abandonar la página.
