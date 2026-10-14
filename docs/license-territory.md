# Ámbito territorial de licencias

El contrato `license-territory-v1` se ejecuta en cada ingesta municipal, colección Madrid,
exportación Supabase y generación local web. Python y JavaScript usan las mismas reglas;
las pruebas comprueban Madrid acreditado, Valladolid, desconocidos y conflictos.
Madrid capital se identifica por INE **28079**; Valladolid por **47186**. Otros municipios
conservan su slug acreditado; no se les inventa un código INE.

`source=madrid-opendata` corresponde al adaptador registrado del dataset municipal
300193. El descargador nuevo guarda URL exacta del recurso, adaptador y municipio en
`_territorial_origin`. Los adaptadores municipales guardan el portal del manifest. La
combinación explícita municipio + fuente es evidencia de los contratos anteriores.
Un slug aislado, las coordenadas, el NDP, el nombre del fichero y el origen nulo no
acreditan Madrid. Evidencias incompatibles producen cuarentena. `_territory` es un
resultado derivado, nunca una fuente de evidencia; el original permanece en raw_json.

El exportador filtra antes de años, clasificación, estadísticas y puntos. Publica código
municipal por fila y feature. Índice, años, total y cobertura se calculan del mismo conjunto;
`withoutCoords` explica la diferencia mapa/total. El informe territorial enumera las
exclusiones y motivos sin publicar el registro original. La construcción del dashboard,
filas compactas y builds con SKIP_BUILD_DATA rechazan particiones antiguas, códigos
extraños o totales descuadrados. Una excepción del normalizador ocurre antes de escribir
artefactos; el job falla y conserva el juego anterior. Una corrección que vacía un año
retira sus ficheros. No se reutiliza silenciosamente un export fallido.

## Replay inicial y posteriores cambios de regla

No se ha ejecutado ninguna escritura en producción desde esta PR.

1. Regenerar evidencia desde los XLSX municipales con el descargador actualizado
   (`python -m sector_geometry.madrid_licencias_download --skip-download`).
   Los XLSX deben proceder de las URLs registradas; no etiquetar el JSONL histórico a mano.
2. Ejecutar `python db/replay_license_territory.py --evidence-jsonl output/madrid_licencias.jsonl`.
   Es lectura únicamente. Sin evidencia también funciona: los desconocidos se mantienen
   excluidos. El emparejamiento compara todos los campos originales, no solo claves.
3. Revisar los conteos. En el entorno de operación autorizado, el mismo comando con
   `--apply` actualiza municipio y resultado derivado en una transacción, manteniendo raw.
   Repetirlo con iguales fuentes y reglas no cambia registros.
4. Reexportar desde Supabase y ejecutar build-data; comprobar el informe de exclusiones
   y el guardia `node web/scripts/assert-license-territory.mjs`.

La migración `20261014220000_license_territory_queue.sql` invalida ambos scopes al cambiar
un municipio. La cola tiene una fila por municipio, también para el anterior. Consulta
operativa: `SELECT * FROM homes.license_territory_rebuild ORDER BY requested_at`.
El export Madrid siempre reconstruye su conjunto completo con el contrato actual, sin
confiar en esta cola. **Pendiente para cierre completo:** conectar un consumidor de la cola
que regenere todos los otros scopes municipales y confirme su publicación; añadir una
reconciliación diaria de publicaciones. La actualización automática existente de Madrid
continúa en su calendario semanal/mensual. No presentar la cola como un consumidor.

## Validación

`python -m unittest discover -s db -p test_license_territory.py`

`node web/scripts/test-license-territory.mjs`

Estos tests no necesitan credenciales. Se prueban cuarentena, Valladolid con coordenadas
aparentemente madrileñas, reconciliación, retirada de particiones al cambiar municipio,
fallo conservando el artefacto anterior y recuperación. La migración necesita validación
de integración PostgreSQL antes de aplicarse; no se ha aplicado desde esta PR.

## Integración con otras correcciones

H01 / PR #859 cambia la lectura a `homes.licencia_actividad`; mantener ese nombre y
las nuevas columnas territoriales en SELECT. Sus marcadores `_entity_policy` deben
conservarse junto con `_territory`. H02 / #857 modifica bloques de proyectos y no
cambia este contrato. H03 / #858 normaliza coordenadas dentro de save_licencias;
conservar ambas validaciones (territorio no se deduce de coordenadas). H05 / #854
modifica fechas, raw y particiones: componer marcadores y mantener el filtro territorial
antes de elegir el año. La integración H05 conserva conjuntamente los contratos territorial y geográfico,
y mantiene el alcance estadístico H06. La relación con cambios aún no integrados
debe revisarse contra el SHA de main usado en el merge.

## Transición del snapshot versionado y compilación Vercel

La publicación Vercel usa `build:public` con `SKIP_BUILD_DATA=1`, sin acceso a DB.
Se entrega el juego completo acreditado que requiere ese camino: índice, filas JSON,
GeoJSON, filtro, dashboard y presentación. No se elimina el guardia territorial.

Para reconstruirlo desde el caché original del descargador oficial:

```
python -m sector_geometry.madrid_licencias_download --skip-download
node web/scripts/rebuild-cached-license-snapshot.mjs
node web/scripts/assert-license-territory.mjs
```

El primer comando exige XLSX locales en `output/madrid_licencias_raw/`; en esta revisión
se copiaron preservando mtime desde el caché autorizado de trabajo. Los recursos y sus
SHA256 se conservan en `madrid-licencias-index.json.sourceSnapshot.resources` y en el
linaje de cada fila de ingestión. `cacheModifiedAt` registra el mtime del fichero cacheado:
**no es una fecha factual de actualización municipal**. `generatedAt` es la hora del
reproceso. `downloadedThisRun=false`, `mode=cached-xlsx-replay` y `factualUpdatedAt=null`
explicitan que esta revisión no ha descargado una actualización factual.

El snapshot nuevo tiene **48.960** licencias de los ejercicios de dataset **2022–2026**:
18.467 / 6.538 / 8.811 / 11.496 / 3.648. Se usa `minYear=2022`, el ámbito que ya exigía
el build público. Índice, dashboard, filtro y presentación usan las mismas 48.960 filas.
El mapa cubre 47.762; 1.198 carecen de coordenadas válidas. H05 retira el supuesto cierre de abril de 2026 basado en volumen. Sin evidencia de
cierre y paginación, `lastCompleteMonth=null`, la cobertura es parcial y no hay
comparativas de meses completos. Reconstruir en octubre no acredita cierre.

El corte previo auditado de 59.374 mezclaba territorios; no constituye una comparación
factual de actividad con este replay. Los GeoJSON heredados 2015–2021 se retiran del
snapshot público, junto con el año inválido 8202, para que ningún mapa antiguo eluda el
índice del ámbito 2022+. El histórico XLSX completo se conserva fuera del snapshot
público para reprocesos posteriores.

La transición de `statisticsScope` de H06/#860 permanece activa junto con esta guardia.
No se cambian sus denominadores ni fechas de evidencia al reconstruir las licencias.

Validación de transición realizada desde un clon limpio con dependencias físicas (sin
symlink), sin `SUPABASE_DB_URL` ni `DATABASE_URL`: `npm run build:public` completa
prebuild, guardias territorial y H06, Turbopack, TypeScript y generación de páginas.
La interfaz distingue la generación del panel del origen factual: muestra que las
licencias se reconstruyeron desde archivos conservados y que no se verificó su fecha
de actualización municipal.
