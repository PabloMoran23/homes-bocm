# Automation: merge de PRs municipio (babysitter)

Cursor Automation que cada **3 días** revisa PRs abiertas de onboarding, valida adapters, mergea las aptas y deja el post-merge en **GitHub Actions**.

## Archivos

| Archivo | Rol |
|---------|-----|
| `.cursor/automations/merge-municipio-prs.yaml` | Cron + repo |
| `.cursor/prompts/merge-municipio-prs.md` | Prompt (pegar en UI) |
| `.github/workflows/municipio-post-merge.yml` | **Post-merge en push a main** (queue + pipeline + Supabase) |
| `.github/workflows/validate-municipio-pr.yml` | CI estático en cada PR |
| `municipio/merge_babysitter.py` | Inventario PRs (`merge-review`) |
| `scripts/post-merge-municipio.sh` | Lógica post-merge (usada por GHA) |
| `scripts/ci/detect-municipio-push-slugs.sh` | Detecta slugs en push |

## Secretos GitHub (ya configurados)

| Secret | Uso |
|--------|-----|
| `SUPABASE_DB_URL` | Pipeline + sync en `municipio-post-merge.yml` |

No hace falta pasar la URL a Cursor Automations.

## Activar babysitter en Cursor

1. [cursor.com/automations](https://cursor.com/automations) → **nueva automation**
2. Repo `PabloMoran23/homes-bocm`, rama `main`
3. Cron: `0 9 */3 * *`
4. Pega `.cursor/prompts/merge-municipio-prs.md`
5. **Sin** `SUPABASE_DB_URL` en Secrets de Cursor

## Flujo completo

```
[Onboard / 4h]     claim → adapter → PR (sin queue.yaml)
[Merge bot / 3d]   validate → gh pr merge
[GitHub Actions]   push main → municipio-post-merge → queue done + sync
[Admin /admin]     export-admin (local) muestra estado
```

## Workflow `Municipio post-merge`

**Trigger:** push a `main` que toque `data/municipios/**/manifest.yaml` o `municipio/adapters/**`

**Manual:**

```bash
gh workflow run municipio-post-merge.yml -f slug=coin
gh run list --workflow=municipio-post-merge.yml
```

## Comandos locales

```bash
PYTHONPATH=. python3 -m municipio merge-review
./scripts/post-merge-municipio.sh coin   # solo local; en prod usa GHA
```
