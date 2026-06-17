# Automation: onboarding de portales municipales

Cursor Automation que cada **4 horas** toma el siguiente municipio de la cola BOCM, investiga su portal, implementa el adapter de ingesta, sincroniza a Supabase y abre PR.

## Archivos

| Archivo | Rol |
|---------|-----|
| `.cursor/automations/onboard-municipio-ayuntamiento.yaml` | Definición de la automation (cron + repo + tools) |
| `.cursor/prompts/onboard-municipio-ayuntamiento.md` | Instrucciones detalladas para el agente |
| `data/municipios/queue.yaml` | Cola de municipios CM ordenada por volumen BOCM |
| `municipio/queue.py` | Lógica de cola (claim / done / fail) |
| `db/sync_municipio_to_supabase.py` | Portal JSONL → `homes.proyecto` + `homes.licencia` |

## Activar en Cursor

La definición YAML vive en el repo, pero hay que **activarla** en Cursor:

1. Abre [cursor.com/automations](https://cursor.com/automations) o la pestaña **Automations** en la ventana de Agents.
2. **Importa** o crea una automation basada en `.cursor/automations/onboard-municipio-ayuntamiento.yaml`.
3. Configura:
   - **Repositorio:** `PabloMoran23/homes-bocm`, rama `main`
   - **Trigger:** cron `0 */4 * * *` (cada 4 horas)
   - **Tools:** Memories (opcional). No hay "crear PR" — el agente usa `gh pr create` (ver prompt).
   - **Prompt:** apunta a `.cursor/prompts/onboard-municipio-ayuntamiento.md` o pega su contenido
4. **Run Now** para probar con el primer municipio (`torrejon-de-ardoz`).
5. Revisa la PR generada antes de mergear.

### Variables de entorno (opcional)

Para que el agente ejecute sync real a Supabase, configura en la automation o en el dashboard:

```
SUPABASE_DB_URL=postgresql://...
```

Sin esto, el agente deja el código listo y documenta sync manual en la PR.

## Cola de municipios

Estado actual (46 municipios CM con ≥20 proyectos BOCM):

- **done:** Pozuelo, Móstoles, Getafe (adapters piloto)
- **skipped:** Madrid capital (pipeline SIGMA propio)
- **pending:** resto, empezando por Torrejón de Ardoz

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
claim → investigar portal → manifest + adapter → run pipeline → sync supabase → PR → queue done
```

### Pipeline completo (manual)

```bash
PYTHONPATH=. python -m municipio run --municipio <slug> --step all
python3 db/sync_municipio_to_supabase.py --municipio <slug>
python3 db/export_web_data_from_supabase.py   # opcional, requiere SUPABASE_DB_URL
```

## Coste

Las automations usan **cloud agents** (Max Mode). Cada municipio es una run de ~15-30 min según complejidad del portal. Con cron cada 4h procesas ~6 municipios/día como máximo.

## Referencias

- `data/municipios/SUBAGENT-BRIEF.md` — contrato del adapter
- `municipio/adapters/pozuelo.py` — referencia Drupal
- `municipio/adapters/mostoles.py` — referencia tablón sede
- `municipio/adapters/getafe.py` — referencia gobierno abierto
