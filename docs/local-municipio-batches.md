# Onboarding local por lotes de 50

El orquestador reserva municipios por identidad INE y distribuye trabajo entre subagentes. Cada trabajador investiga, crea el adaptador y entrega evidencias. El orquestador revisa y agrupa exactamente 50 municipios aceptados en una PR. Los bloqueados liberan capacidad del lote para reservar sustitutos, pero siguen registrados y no se reintentan automáticamente.

`scripts/local_municipio_batches.py` usa Python 3 y PyYAML. No ejecuta scrapers, modifica la cola del repositorio, hace push, abre PR, fusiona ni publica datos. Sus operaciones son simuladas salvo `--apply`. El ledger JSON y su archivo `.lock` se guardan fuera del repositorio. `flock`, escritura temporal y reemplazo atómico protegen reservas entre procesos en el mismo host. Todos los trabajadores deben usar el mismo ledger y la misma ruta `--repo`; sus worktrees de implementación pueden ser independientes.

## Preparación y reservas

Desactivar previamente la automatización de Cursor y obtener un inventario reciente de PR abiertas, incluyendo todos sus archivos. El snapshot esperado es una lista JSON con objetos `files: [{path: "..."}]`; los resultados truncados no son un inventario válido. No iniciar otra cola independiente sobre los mismos municipios.

```bash
REPO=/ruta/al/worktree-orquestador
STATE=/ruta/fuera/del/repositorio/municipios-ledger.json
INE=/ruta/al/padron/municipios.json
PRS=/ruta/al/snapshot-prs.json

# Primero inspeccionar sin persistir.
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" init --ine "$INE" --open-prs "$PRS"
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" --apply init --ine "$INE" --open-prs "$PRS"

python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" --apply reserve --batch batch-001 --worker worker-a --count 10
# Opcional: asignar un candidato concreto en lugar de los primeros de la cola.
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" --apply reserve --batch batch-001 --worker worker-b --slug manlleu
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" status
```

`init` rechaza sobrescribir un ledger existente. Para reanudar, usar `status` y las asignaciones existentes. Se conserva el orden de la cola; solamente se incluyen entradas `pending`, identificadas sin ambigüedad por nombre y provincia del padrón. Se excluyen manifests y PR abiertas por slug e identidad resuelta. Los alias no reconciliados se omiten; no se infieren identidades dudosas. El inventario es un snapshot inicial: antes de integrar, volver a comprobar `main` y PR abiertas. El ledger no detecta trabajo externo posterior automáticamente.

## Entrega y aceptación

Cada municipio puede añadir exclusivamente:

- `data/municipios/<slug>/manifest.yaml`
- `data/municipios/<slug>/RESEARCH.md`
- `municipio/adapters/<slug_con_guiones_bajos>.py`

También puede añadir una prueba específica `municipio/test_<slug>.py` o
`municipio/adapters/test_<slug>.py`. No se modifican módulos compartidos sin una
revisión separada del orquestador.

El manifest debe incluir explícitamente `schedule.enabled: false` y `geocode.jitter_missing: false`. No usar centroides o jitter como geometría de registros. No ejecutar publicación, ingestión Supabase ni scripts post-merge. Las comprobaciones en vivo deben ser locales, acotadas y conservar resultados fuera del repositorio.

Antes de aceptar código, revisar sintaxis/importación, extracción real de registros legítimos, procedencia y evidencia reproducible. Cero registros, formularios vacíos, fuentes inaccesibles o un scraper que no funciona se marcan `blocked`. La ausencia de geometría real no impide aceptar código útil: documentar `publication_ready: false` y la cobertura pendiente en la evidencia. La aceptación de código no autoriza activar el schedule ni publicar. El pipeline `scripts/ci/municipio_batch.py` sin `--publish` puede añadir validación de publicación en staging; sus requisitos de geometría no equivalen a los de aceptación del código.

```bash
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" --apply set-status --ine-code 08112 --worker worker-b --status review --evidence /ruta/evidencia/manlleu.json
# Solo el orquestador, después de revisar e integrar los archivos localmente:
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" --apply set-status --ine-code 08112 --worker worker-b --status accepted --evidence /ruta/revision/manlleu.json
```

El helper registra la declaración de revisión y comprueba las opciones seguras del manifest; no certifica la extracción ni interpreta el texto de `--evidence`. El orquestador debe comprobar esas evidencias y el guard de integración antes del merge. El campo `worker` es control de coherencia, no autenticación.

Para bloquear usar `set-status --status blocked --evidence "motivo concreto"`. Las reservas no caducan automáticamente. Tras comprobar que un trabajador ha parado, se puede ejecutar explícitamente `release --ine-code ... --worker ... --reason "..."`; conserva un historial y devuelve el municipio a pendientes. No liberar una reserva mientras el trabajador sigue ejecutándose.

## Integración sin despliegue

Preparar cada PR en una rama limpia con una base fijada. El bootstrap del controlador debe quedar fuera del diff del lote: esta validación solo admite archivos nuevos municipales. Los cambios de infraestructura, queue, web, workflows, archivos existentes y symlinks se rechazan.

```bash
python3 "$REPO/scripts/local_municipio_batches.py" --repo "$REPO" --ledger "$STATE" validate-batch --batch batch-001 --base COMMIT_BASE
```

Se requieren exactamente 50 aceptados. El límite de reserva cuenta `assigned`, `review` y `accepted`; permite sustituir bloqueados sin sobrepasar 50 plazas activas. No completar un lote con municipios bloqueados para llegar al número.

Antes de push/merge, comprobar también la configuración remota con el guard del orquestador: workflows de despliegue sin trigger de push/PR aplicable, filtro Vercel vigente y commit final con `[skip deploy]`. En la configuración inspeccionada, `municipio-post-merge.yml` es manual, Vercel respeta `[skip deploy]`, y `refresh-municipios.yml` sí tiene cron; por eso los nuevos schedules permanecen desactivados. No despachar workflows manualmente. Volver a revisar si cambia la base. Un snapshot local de YAML por sí solo no prueba que no existan integraciones externas de despliegue.

### Control final antes de publicar la rama o fusionar

`scripts/local_municipio_preflight.py` es el guard completo de la rama agregada.
Requiere checkout limpio, exactamente 50 identidades INE aceptadas, archivos nuevos
del lote, evidencias JSON con hashes del código revisado, la base igual al `main`
remoto actual, ausencia de PRs rivales y una auditoría externa de despliegues de
menos de 24 horas. Admite explícitamente el bootstrap de estas herramientas y sus
pruebas en el primer lote. El helper `validate-batch` anterior es una comprobación
más estrecha para diffs que contengan solamente los tres entregables municipales.

Cada `review.json` del orquestador contiene `slug`, `code_accepted: true`,
`static_ok: true`, `live_records >= 1`, `published: false` y `files_sha256` para
manifest, adapter y RESEARCH. Añadir URLs, limitaciones, pruebas y
`publication_ready` para distinguir extracción de publicación.

```bash
python3 scripts/local_municipio_preflight.py --ledger "$STATE" \
  --batch batch-001 --base SHA_MAIN \
  --deployment-audit /ruta/deployment-audit.json
```

El control verifica que Vercel devuelve explícitamente `skip` tanto para preview
como para production. Si falla cualquier comprobación, no hacer push ni merge.
El orquestador crea una única PR del lote y la adjunta al chat, vuelve a comprobar
su SHA y la base antes de fusionar y usa un título de merge que conserve
`[skip deploy]`. Después verifica por SHA que Vercel no ha publicado y que no se
ha ejecutado un workflow de escritura. Los registros de despliegue cancelados
por el filtro son esperables. No se despachan los jobs manuales de publicación.

No hay un daemon oculto: el controlador distribuye y registra trabajo, y los
subagentes del chat ejecutan las investigaciones mientras este chat trabaja.
Para reanudar otra sesión hay que leer el ledger y continuar las asignaciones;
las reservas no se liberan automáticamente al terminar una conversación.

Pruebas del controlador:

```bash
python3 -m unittest discover -s tests -p 'test_local_municipio*.py' -v
```
