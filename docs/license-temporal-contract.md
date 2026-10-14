# Licencias: fechas y cierre de periodos (H05)

Contrato `license-dates-v1`: `db/license_dates.py` y `web/scripts/lib/license-dates.mjs`. Admite `YYYY-MM-DD`, `D/M/YYYY`, `YYYY-MM` y año de cuatro cifras; valida calendario gregoriano y años 1900–2100. No interpreta años cortos ni fabrica días cuando la precisión es mensual/anual. Las fechas observadas cuya primera fecha posible supera el corte UTC van a cuarentena. `planned` admite previsiones futuras, pero las licencias usan siempre `observed`.

Las ingestas municipales y el colector Madrid aplican el contrato en cada ejecución; mantienen originales y resultados en `raw_json.temporal`. Un campo inválido se escribe como NULL y retira el valor anterior. Los exportadores reevalúan originales para permitir recuperación o cambios de regla. Una concesión explícita inválida no se reemplaza por una fecha de alta para datar actividad.

Cada build público comprueba fixtures Python/JS antes de modificar derivados; errores de contrato o JSON inválido hacen fallar el build. Los exportadores reconstruyen todos los años desde el snapshot y retiran particiones anteriores que quedan vacías. El filtro también se reconstruye completo: una corrección invalida ambos periodos y no suma resultados a agregados antiguos. `madrid-license-temporal-quarantine.json`, `madrid-filter-temporal-quarantine.json` y los logs indican campos excluidos.

## Evidencia de cierre

El filtro publica `temporal.inputDigest` (datos anuales + versión de regla), corte, reconstrucción `full` y `periodCoverage`. `madrid-period-coverage.json` puede contener evidencia del cierre **de toda la fuente**, ligada al snapshot:

```json
{"periods":{"2025-02":{"status":"complete","sourceClosed":true,"paginationComplete":true,"inputDigest":"HASH_DEL_SNAPSHOT","evidence":"URI o identificador del informe de cierre de la fuente"}}}
```

Todas las condiciones deben cumplirse y el mes debe haber terminado en el corte UTC. Un cambio de datos/reglas invalida el digest. Evidencia ausente, paginación pendiente, mes actual o digest diferente producen `partial`. El volumen nunca acredita cierre (regresión con 401 filas). El scraper actual no aporta ese certificado: sus periodos se presentan parciales. No crear certificados a partir de recuentos.

La presentación compara sólo meses acreditados comunes entre años; sin ellos omite la comparativa. El KPI mensual requiere cierre del mes calendario anterior y del actual. El anual utiliza meses comunes cerrados. Sin cierre muestra el recuento observado parcial, sin porcentaje. La evolución conserva estado por periodo y texto de cobertura parcial.

## Brecha pendiente para cerrar H05

`sync_madrid_public_to_supabase.licencia_key` contiene fecha de concesión/año. En modo incremental una corrección del origen puede crear otra identidad y dejar la antigua en la base. Falta un identificador estable o evidencia de snapshot completo para reconciliar sin borrar registros legítimos. Este cambio normaliza valores, pero no migra esa identidad. La reconstrucción completa invalida derivados sobre el snapshot recibido; no resuelve duplicados ya presentes en la base. El PR referencia H05 sin cerrarla. No se ejecuta reproceso de producción ni se certifican cierres sin evidencia.

Pruebas: `python db/test_license_dates.py`, `npm --prefix web run test:license-dates`, TypeScript y ESLint. Cubren ingesta/export, calendario, precisión, cuarentena, repetición, corrección entre años, retirada de partición, fallo/recuperación y comparativas parciales.

## Integración del snapshot territorial

El replay del caché acreditado conserva 48.960 filas de 2022–2026, 47.762 puntos y
1.198 filas sin coordenadas. La procedencia se propaga a índice, filtro, dashboard
y presentación; `factualUpdatedAt=null` conserva la falta de fecha factual municipal.
Las marcas `generatedAt` corresponden a la ejecución real de cada builder. No hay
evidencia de cierre: se publica `lastCompleteMonth=null`, cobertura parcial y
comparativa vacía, retirando el supuesto cierre de abril basado en volumen.

`assert-license-temporal.mjs` se ejecuta también con `SKIP_BUILD_DATA=1`: comprueba
contrato, totales, procedencia y meses comparables sobre los JSON versionados. La
regresión rechaza una presentación con abril de 2026 indebidamente cerrado.
