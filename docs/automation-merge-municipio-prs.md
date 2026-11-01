# Revisión e integración por lotes de municipios

El onboarding se revisa por lotes. Fusionar incorpora los manifests y adapters;
no ejecuta scrapers ni publica datos. El refresco programado descubre los nuevos
manifests automáticamente.

## Inventario del backlog

```bash
python tools/review_municipio_backlog.py --fetch --output output/backlog-review.json
```

Las señales del inventario requieren revisión: una fecha de metadatos puede ser
correcta aunque contenga `datetime.now`. Ausencia de señales no equivale a aprobación.
Excluir duplicados ya presentes en main, cambios fuera de alcance y conflictos
semánticos. Los alias territoriales requieren revisión específica.

## Preparación de un lote

1. Trabajar en una rama aislada, agrupando solo PRs revisadas. Preservar los
   commits originales mediante merges y conservar únicamente los archivos
   municipales aprobados; descartar los cambios de `queue.yaml` de las PRs.
2. No presentar formularios como licencias ni completar fechas anuales con días
   inventados. `municipio.onboarding_snapshot.reviewed_records` sirve para los
   adapters revisados; no altera automáticamente todos los adapters existentes.
3. Declarar el CRS de salida comprobando la petición o transformación del adapter.
   Desactivar `geocode.jitter_missing` en los municipios nuevos: los puntos alrededor
   del centro municipal no demuestran la ubicación de un proyecto.
4. Para la revisión mínima de un lote, comprobar estáticamente los manifests y
   adapters sin ejecutar scrapers. Una extracción de prueba es una acción adicional
   y debe hacerse solo si se ha solicitado; se puede ejecutar de forma aislada con
   un plazo por municipio:

```bash
python scripts/ci/municipio_batch.py run 'slug-uno slug-dos' --workers 4 --timeout 600
```

Cada proceso obtiene una sola instantánea completa, en lugar de repetir backfill
más update. Los fallos no impiden validar los otros municipios. El dry-run nunca
actualiza la cola ni escribe en Supabase. Revisar `output/municipio-batch/`.

5. Incluir en la PR de integración solamente los municipios aptos y conservar
   aparte el informe de bloqueos. La CI valida todos los manifests y también
   las modificaciones que solo toquen el adapter.
6. Fusionar la PR de integración con un **merge**, conservando los commits fuente.
   Esto permite a GitHub reconocer las PRs originales integradas. No usar squash
   para esta PR agregada ni marcar como integradas PRs que se hayan excluido.
7. Si el lote debe incorporarse sin despliegue, incluir `[skip deploy]` en el
   mensaje del commit final que llega a `main` (también en el merge). El Ignored
   Build Step de Vercel respeta esa marca incluso si falta el SHA anterior o si
   el lote incluye cambios en `web/`. Sin la marca sigue aplicándose el filtro
   habitual de archivos y su comportamiento ante errores.

## Refresco posterior

`refresh-municipios.yml` mantiene su cron cada cuatro horas y procesa hasta
20 municipios por ejecución. `municipio.schedule.due_plan` enumera todos los
manifests, excluye Madrid y los que declaran `schedule.enabled: false`, y prioriza
los que no tienen `last_ingest_at` en Supabase. No hay que ejecutar un scraper al
fusionar ni insertar manualmente una entrada en la base de datos.

El estado de `data/municipios/queue.yaml` corresponde al seguimiento del onboarding;
no determina la selección de la cola de refresco. Un nuevo manifest habilitado
queda disponible para la próxima ejecución programada. No marcarlo como publicado
antes de que termine correctamente su extracción y sync.

El workflow `Municipio post-merge` solo admite ejecución manual; no tiene trigger
por push. Su publicación inmediata se reserva para una petición explícita y se
puede lanzar con una lista separada por comas:

```bash
gh workflow run municipio-post-merge.yml -f 'slug=slug-uno,slug-dos'
```

Ese dispatch ejecuta extracción, validación y publicación a Supabase; no forma
parte de la integración de PRs. La publicación utiliza el secret del repositorio
en GitHub Actions. Sus informes individuales quedan como artifacts y solo las
publicaciones confirmadas actualizan la cola de onboarding.
