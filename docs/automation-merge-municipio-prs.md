# Revisión e integración por lotes de municipios

El onboarding se revisa por lotes. La cola se conserva desde `main` hasta que la
extracción, la validación geográfica y el sync hayan terminado correctamente.

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
4. Ejecutar la extracción aislada con un plazo por municipio:

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

## Publicación posterior

El workflow `Municipio post-merge` detecta todos los slugs desde el rango completo
del push y desde los adapters modificados. Ejecuta cuatro procesos concurrentes,
con un límite de diez minutos por municipio. Solo publica instantáneas con
proyectos, coordenadas, paridad suficiente y sin geografía en cuarentena.

Cada worker publica un municipio de forma independiente. Solo el proceso padre
marca como `done` las publicaciones confirmadas; un fallo conserva pendientes
las entradas correspondientes y no elimina los éxitos de los otros workers.
La cola se guarda incluso si parte del lote falla, y los logs e informes quedan
adjuntos como artifact de Actions. Un workflow fallido puede contener municipios
publicados correctamente: consultar el resumen individual.

Para reintentar los fallidos, el dispatch admite una lista separada por comas:

```bash
gh workflow run municipio-post-merge.yml -f 'slug=slug-uno,slug-dos'
```

No es necesario pasar credenciales de Supabase al agente local. La publicación
utiliza el secret del repositorio en GitHub Actions.
