# Merge PRs municipio (babysitter)

Eres un agente de Cursor en el repo `homes-bocm` (`poc-bocm/`). Tu trabajo es **revisar PRs abiertas de onboarding de municipios**, validarlas, **mergear las que pasen** y **cerrar el ciclo en `main`** para que el panel admin (`/admin/municipios`) refleje el estado.

**No implementes municipios nuevos.** Solo revisión + merge + post-merge.

---

## Paso 0 — Contexto

```bash
cd poc-bocm   # raíz del repo clonado
git fetch origin
git checkout main
git pull origin main
pip install -r requirements-municipio.txt
```

Variables útiles en el entorno del agente:

```
GITHUB_TOKEN=...   # gh auth en cloud agents suele venir preconfigurado
```

**No necesitas `SUPABASE_DB_URL` en Cursor.** Tras merge a `main`, el workflow **Municipio post-merge** (GitHub Actions) ejecuta pipeline + sync con el secret del repo.

---

## Paso 1 — Inventario de PRs

```bash
PYTHONPATH=. python3 -m municipio merge-review
```

Interpreta el JSON:

- `candidates[]` — PRs abiertas de portales municipales
- `slug` — municipio detectado (rama `automation/municipio-<slug>` o manifest en el diff)
- `checksSummary.allGreen` — CI de GitHub verde
- `mergeable` — debe ser `MERGEABLE`

Si no hay candidatas, termina: **"Sin PRs municipio pendientes de merge."**

---

## Paso 2 — Procesar **una PR por ejecución** (evita conflictos en `queue.yaml`)

Orden de prioridad:

1. PR con checks verdes y `mergeable=MERGEABLE`
2. Si varias, la de **número más bajo** (más antigua)

Para la PR elegida (`NUMBER`, `SLUG`, `URL`):

### 2a. Checkout de la rama

```bash
gh pr checkout NUMBER
```

### 2b. Check estático (rápido)

```bash
chmod +x scripts/check-municipio-pr-static.sh scripts/validate-municipio-onboard.sh scripts/post-merge-municipio.sh
./scripts/check-municipio-pr-static.sh SLUG
```

Falla si falta manifest, RESEARCH, adapter o import roto.

### 2c. Validación completa (scrape + parity)

```bash
./scripts/validate-municipio-onboard.sh SLUG
```

Criterios mínimos para merge:

- `parity overall` ≠ `none`
- `proyectos` ≥ 1 fila
- `with_coords` ≥ 1

Si `overall=partial` pero hay datos reales (proyectos + coords), **puedes mergear** y documentar limitaciones en comentario de PR.

Si falla por portal caído / timeout: **no mergear**. Comenta en la PR y opcionalmente:

```bash
git checkout main
PYTHONPATH=. python3 -m municipio queue fail --municipio SLUG --error "validación fallida: <motivo>"
```

(abre issue en comentario, no cierres la PR sin explicación)

### 2d. Revisar diff (scope)

La PR solo debe tocar:

- `data/municipios/SLUG/**`
- `municipio/adapters/*.py` (el del municipio)
- **No debe** incluir `queue.yaml` marcado como `done` (lo hace post-merge en main)
- **No debe** tocar `web/`, `output/`, `.github/` salvo bugfix acordado

Si hay cambios fuera de scope → comentar y **no mergear**.

### 2e. CI GitHub

```bash
gh pr checks NUMBER
gh pr view NUMBER --json mergeable,reviewDecision,statusCheckRollup
```

Espera/reintenta si checks `pending`. Merge solo si workflow **Validate municipio PR** (estático) está verde.

---

## Paso 3 — Merge

```bash
gh pr merge NUMBER --squash --delete-branch --subject "feat(municipio): portal ayuntamiento <Nombre>"
```

Si `--merge` falla por conflictos:

```bash
git checkout main && git pull
gh pr checkout NUMBER
git merge origin/main
# resolver solo conflictos triviales en adapter/manifest; si queue.yaml conflicta, quédate con main y no incluyas queue en la PR
git push
```

Re-ejecuta checks y reintenta merge.

---

## Paso 4 — Post-merge (GitHub Actions, automático)

**No ejecutes `post-merge-municipio.sh` en el agente.** Tras `gh pr merge`, GitHub dispara el workflow **Municipio post-merge** en push a `main`:

1. Detecta el slug desde `data/municipios/<slug>/manifest.yaml`
2. `queue done` + pipeline `--step all` + sync Supabase (`SUPABASE_DB_URL` en secrets del repo)
3. Commit de `data/municipios/queue.yaml` en `main`

Comprueba el run:

```bash
gh run list --workflow=municipio-post-merge.yml --limit 3
gh run watch   # opcional, con RUN_ID
```

Si el workflow falla (portal caído, scrape timeout), reintenta manualmente:

```bash
gh workflow run municipio-post-merge.yml -f slug=SLUG
```

Comenta en la PR mergeada (si aún editable):

> Mergeado por automation babysitter. Post-merge en GitHub Actions workflow `municipio-post-merge`.

---

## Reglas

- **Máximo 1 merge por ejecución** (esta automation corre cada pocos días; el backlog se vacía en varias runs).
- **No fuerces merge** si parity `none` o 0 proyectos.
- **No toques** pipeline Madrid capital (`sector_geometry/madrid_*`).
- Prefiere `--squash` para historial limpio.
- Si la PR es claramente basura (adapter vacío, portal inventado): cierra con comentario y `queue fail`, no merge.

---

## Criterios de éxito de la run

- [ ] Inventario PRs ejecutado (`merge-review`)
- [ ] 0 o 1 PR mergeada con validación documentada
- [ ] Workflow **Municipio post-merge** verde en GitHub Actions (o reintento manual)
- [ ] Resumen final: PR URL, slug, parity, enlace al run de Actions

---

## Comandos de referencia

```bash
PYTHONPATH=. python3 -m municipio merge-review
PYTHONPATH=. python3 -m municipio export-admin   # payload panel admin
gh pr list --state open --label "" 
gh pr checks NUMBER
```
