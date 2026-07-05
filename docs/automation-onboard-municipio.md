# Automation: onboarding de portales municipales

Cursor Automation que cada **4 horas** toma el siguiente municipio de la cola BOCM, investiga su portal, implementa el adapter de ingesta (incl. geometría del visor si existe), sincroniza a Supabase y abre PR.

## Archivos

| Archivo | Rol |
|---------|-----|
| `.cursor/automations/onboard-municipio-ayuntamiento.yaml` | Onboarding cada 4h |
| `.cursor/automations/merge-municipio-prs.yaml` | Merge/revisión cada 3 días |
| `.cursor/prompts/onboard-municipio-ayuntamiento.md` | Prompt onboarding |
| `.cursor/prompts/merge-municipio-prs.md` | Prompt merge babysitter |
| `data/municipios/queue.yaml` | Cola de municipios (BOCM + CCAA) ordenada por volumen en boletines |
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

El sync a Supabase **no corre en Cursor** — lo hace GitHub Actions tras merge (`municipio-post-merge.yml`) con el secret `SUPABASE_DB_URL` del repo.

## Cola de municipios

La cola se genera desde los CSV parseados (`output/history_parsed_incremental.csv` + `output/ccaa_history_parsed_incremental.csv`), no desde `summary.json` (que solo guarda el top 50).

**Sin umbral mínimo:** entra cualquier municipio con **≥1 fila parseada** (~845 hoy). Se ordena por volumen (`bocm_count` descendente) para que los bots empiecen por los más activos. Metadata: `boletin_source_id`, `comunidad_autonoma`, `provincia`.

Estado tras regenerar con `queue init`:

- **done:** municipios con adapter ya mergeado en `main`
- **skipped:** Madrid capital (pipeline SIGMA propio)
- **pending:** resto (~800), ordenados por volumen en boletines

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

# Reinicializar cola completa desde CSVs BOCM + CCAA (≥1 aparición)
PYTHONPATH=. python3 -m municipio queue init

# Opcional: filtrar por volumen mínimo
PYTHONPATH=. python3 -m municipio queue init --min-count 10

# Legacy: solo top 50 de summary.json
PYTHONPATH=. python3 -m municipio queue init --from-summary --min-count 20

# Marcar completado tras merge
PYTHONPATH=. python -m municipio queue done --municipio torrejon-de-ardoz --pr-url "https://..."
```

## Flujo por municipio

```
[Onboard bot]  claim → portal → PR (sin tocar queue.yaml)
[Merge bot]    validate → merge → GitHub Actions post-merge (queue + sync)
```

Manual completo:

```bash
PYTHONPATH=. python -m municipio run --municipio <slug> --step all
# incluye geocode + sync_supabase si SUPABASE_DB_URL está en el entorno

# Repetir solo sync (opcional)
python3 db/sync_municipio_to_supabase.py --municipio <slug>
```

Ver también: `docs/automation-merge-municipio-prs.md`

## Coste

Las automations usan **cloud agents** (Max Mode). Cada municipio es una run de ~15-30 min según complejidad del portal. Con cron cada 4h procesas ~6 municipios/día como máximo.

## Referencias

- **`/admin/login`** — panel interno (contraseña `ADMIN_PANEL_PASSWORD`; no enlazado en la nav)
- `data/municipios/SUBAGENT-BRIEF.md` — contrato del adapter
- `municipio/adapters/pozuelo.py` — referencia Drupal
- `municipio/adapters/mostoles.py` — referencia tablón sede
- `municipio/adapters/getafe.py` — referencia gobierno abierto
