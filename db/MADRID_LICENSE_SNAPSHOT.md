# Reconciliar licencias de Madrid

`sector_geometry.madrid_licencias_download --current` descarga ambos CSV completos:
licencias otorgadas (640505) y declaraciones responsables (133556, incluido 2022).
Conserva el histórico anterior a 2023. La clave actual combina dataset, expediente
y NDP, por lo que corregir una fecha no crea otra licencia. Los solapamientos con
el histórico requieren edificio, fecha y tipo coincidentes y candidatos únicos;
los originales se conservan en `_source_variants`.

El paso municipal `sync_supabase` reconcilia ese snapshot con `homes.licencia` en
una transacción. Antes de sustituirlo archiva todas las filas anteriores en
`homes.madrid_license_snapshot_backup`, identificadas por `batch_id`. Conserva IDs
reconocibles, vínculos con proyectos y fechas de inserción. Comprueba la versión
de clasificación, evita snapshots vacíos o caídas de más del 20%, valida las dos
fuentes, bloquea escritores concurrentes y verifica que las filas ajenas al lote
no cambien. Una repetición del mismo contenido y conjunto de claves no escribe.
No activa la política global de clasificación. Durante la sustitución, bajo el
bloqueo de escritores, pausa únicamente los dos triggers derivados de esa tabla:
la clasificación ya está calculada y se registra una sola invalidación territorial
del lote. Restaura su modo original antes del commit; un rollback también revierte
la pausa. Las restricciones y los demás triggers siguen activos.

Para un replay independiente, primero ejecutar sin `--apply`:

```sh
python -m db.madrid_license_snapshot \
  --jsonl output/madrid_licencias.jsonl --report /tmp/madrid-preflight.json
```

Añadir `--apply` para confirmar la transacción. Se requiere `SUPABASE_DB_URL` o
`DATABASE_URL`. Los informes incluyen el hash del snapshot y recuentos mensuales.
Este comando no publica archivos web ni invoca Vercel.

En la primera migración hay filas antiguas sin municipio ni fuente. No basta el
NDP para atribuirlas a Madrid. `legacy_evidence(Path(raw_dir))` contrasta su
identidad con los XLSX originales oficiales y devuelve fingerprints y un
manifiesto de recursos. Guardar un JSON gzip con claves `fingerprints` (lista)
y `resources` y pasar `--evidence /ruta/evidence.json.gz` al preflight y al apply.
Las filas sin coincidencia quedan intactas. Después de esa migración la fuente
y el municipio ya son explícitos y las siguientes sincronizaciones no necesitan
esa evidencia. Los backups de filas contienen datos de origen: guardarlos fuera
de Git junto al informe de ejecución.

Pruebas:

```sh
python -m unittest db.test_madrid_license_snapshot sector_geometry.test_madrid_licencias_current
```

Las pruebas de integración requieren `MADRID_SNAPSHOT_TEST_DB_URL` explícito y
crean tablas desechables en `pg_temp`; no escriben en tablas de producción ni
utilizan sus secuencias. Verifican atomicidad ante fallos, idempotencia, asociación
con edificios y preservación de otras fuentes.
