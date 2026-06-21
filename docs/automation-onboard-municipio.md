# Automation: onboarding de portales municipales

Cursor Automation que cada **4 horas** toma el siguiente municipio de la cola BOCM, investiga su portal, implementa el adapter de ingesta (incl. geometría del visor si existe), sincroniza a Supabase y abre PR.

## Archivos

| Archivo | Rol |
|---------|-----|
| `.cursor/automations/onboard-municipio-ayuntamiento.yaml` | Definición de la automation (cron + repo + tools) |
| `.cursor/prompts/onboard-municipio-ayuntamiento.md` | Instrucciones detalladas para el agente |
| `data/municipios/queue.yaml` | Cola de municipios CM ordenada por volumen BOCM |
| `municipio/queue.py` | Lógica de cola (claim / done / fail) |
| `municipio/geometry.py` | Helpers GeoJSON (`geom_geojson`, bbox, centroide) |
| `municipio/geocode.py` | Asigna `lat`/`lon` (centroide polígono o municipio + jitter) |
| `municipio/sync_supabase.py` | Paso del orquestador que llama al sync |
| `db/sync_municipio_to_supabase.py` | Portal JSONL → `homes.proyecto` + `homes.licencia` |

## Activar en Cursor

La definición YAML vive en el repo como **documentación**, pero la automation se configura en la UI:

1. Abre [cursor.com/automations](https://cursor.com/automations) o la pestaña **Automations** en Agents.
2. Crea/edita la automation (repo `PabloMoran23/homes-bocm`, rama `main`).
3. **Trigger:** cron `0 */4 * * *` (cada 4 horas).
4. **Tools:** Memories (opcional). No hay "crear PR" — el agente usa `gh pr create` (ver prompt).
5. **Instructions / Prompt:** pega **todo** el contenido de `.cursor/prompts/onboard-municipio-ayuntamiento.md` en el campo de texto de la UI.
   - Cursor **no** enlaza automáticamente al fichero del repo; el `.md` es la fuente de verdad en git.
   - Tras cambiar el prompt en el repo, vuelve a copiarlo y pegarlo en la UI (o usa el comando abajo).
6. **Run Now** para probar.
7. Revisa la PR generada antes de mergear.

### Sincronizar prompt repo → UI

```bash
# Imprime el prompt listo para copiar al portapapeles (Linux)
cat poc-bocm/.cursor/prompts/onboard-municipio-ayuntamiento.md | xclip -selection clipboard
# o simplemente abre el fichero y copia todo
```

Cuando actualices geometría u otras reglas en el `.md`, **repega en la automation** antes del próximo cron.

### Variables de entorno (opcional)

Para que el agente ejecute sync real a Supabase, configura en la automation o en el dashboard:

```
SUPABASE_DB_URL=postgresql://...
```

Sin esto, el agente deja el código listo y documenta sync manual en la PR.

## Cola de municipios

Estado actual (46 municipios CM con ≥20 proyectos BOCM):

- **done:** 9 municipios (Pozuelo, Móstoles, Getafe, Torrejón, Alcalá, Alcobendas, Fuenlabrada, Las Rozas, Rivas)
- **skipped:** Madrid capital (pipeline SIGMA propio)
- **pending:** resto, empezando por Torrejón de Ardoz

La cola en `main` solo avanza al **mergear** la PR (el `queue.yaml` actualizado vive en la rama).
Para no repetir municipios con PR abierta sin merge, `claim` consulta GitHub (`gh pr list`)
y **salta** slugs que ya tienen PR abierta con su `manifest.yaml` → pasa al siguiente pending.

### Comandos manuales

```bash
cd poc-bocm
pip install -r requirements-municipio.txt

# Ver estado
PYTHONPATH=. python -m municipio queue status

# Reservar siguiente (lo hace la automation)
PYTHONPATH=. python -m municipio queue claim

# Reinicializar cola desde summary.json
PYTHONPATH=. python -m municipio queue init

# Marcar completado tras merge
PYTHONPATH=. python -m municipio queue done --municipio torrejon-de-ardoz --pr-url "https://..."
```

## Flujo por municipio

```
claim → investigar portal → manifest + adapter → run pipeline (scrape + geocode + sync_supabase + validate) → PR → queue done
```

### Pipeline completo (manual)

```bash
PYTHONPATH=. python -m municipio run --municipio <slug> --step all
# incluye geocode + sync_supabase si SUPABASE_DB_URL está en el entorno

# Repetir solo sync (opcional)
python3 db/sync_municipio_to_supabase.py --municipio <slug>
```

## Coste

Las automations usan **cloud agents** (Max Mode). Cada municipio es una run de ~15-30 min según complejidad del portal. Con cron cada 4h procesas ~6 municipios/día como máximo.

## Referencias

- `data/municipios/SUBAGENT-BRIEF.md` — contrato del adapter
- `municipio/adapters/pozuelo.py` — referencia Drupal
- `municipio/adapters/mostoles.py` — referencia tablón sede
- `municipio/adapters/getafe.py` — referencia gobierno abierto
