# Anuncios de tablón (sedes Gestiona)

Se guardan **todos** los anuncios del tablón de los municipios con sede Gestiona (`*.sedelectronica.es`), sin filtrar por tema. Qué se muestra (radar, fichas) se decide después en la base de datos.

## Flujo

1. `anuncios_update` (paso del orquestador, en `update`, `backfill` y `all`, antes de `enrich_geometry`):
   - `municipio/gestiona_board.py` localiza el tablón (`portal.config.board_url` o el primer host `*.sedelectronica.es` del manifest) y lo lee entero. La primera página trae ~10 anuncios; el resto se carga pulsando «Mostrar más», una llamada AJAX de Wicket con cookie de sesión. `?page=N` **no** pagina. Tope: 60 clics (~600 anuncios).
   - `municipio/anuncio_clase.py` asigna `clase`/`subclase` por reglas (versión `REGLAS_VERSION`).
   - Escribe `output/municipios/<slug>/anuncios.jsonl` y `anuncios_state.json` (`complete` = se leyó el tablón entero).
   - Es auxiliar: si el tablón falla devuelve `status: failed` sin `error`, así que el municipio no se aparca y proyectos/licencias siguen.
2. `sync_supabase` sincroniza además `homes.anuncio` (`db/anuncios.py`), en su propia escritura. Un fallo aquí no invalida la ingesta principal ni toca `last_ingest_at`.

Desactivar en un municipio: `anuncios: {enabled: false}` en el manifest. Forzar otra URL: `anuncios: {board_url: ...}`.

## Tabla `homes.anuncio`

Esquema en `db/schema_anuncio.sql` (también migración `20261126120000_anuncio.sql`; la ingesta lo crea si falta, como la cola de fallos).

- `id`: `gestiona-` + hash de sede y uuid del documento: estable entre lecturas.
- `first_seen_at` / `last_seen_at` / `retirado_at`: el tablón solo muestra lo vigente. Un anuncio que no aparece en una lectura **completa** se marca retirado; si vuelve, se reactiva.
- `clase`, `subclase`, `clase_regla` (`catalogo` | `texto` | `manual`), `clase_version`: se recalculan en cada lectura salvo si `clase_regla = 'manual'`.
- `visible_radar`: `NULL` = sin decidir. La ingesta nunca lo toca.
- `raw`: columnas extra del tablón y datos de captura.

## Clases

`empleo_publico`, `vivienda_protegida`, `expropiacion`, `enajenacion_patrimonio`, `contratacion_adjudicacion`, `contratacion_licitacion`, `ambiental`, `energia`, `planeamiento`, `licencia_actividad`, `licencia_obra` (subclases `primera_ocupacion`, `demolicion`, `suelo_rustico`), `subvencion`, `hacienda_presupuesto`, `normativa`, `convenio`, `organos_gobierno`, `padron_elecciones`, `sancion`, `notificacion`, `bando_aviso`, `urbanismo_otro`, `otros`.

Manda el procedimiento/categoría del catálogo de la sede si da una clase específica; si no, el título y la descripción. Excepciones: si el título nombra planeamiento, expropiación, enajenación, vivienda protegida o energía, manda el título (salvo empleo público). Ojo: en Gestiona «Licencias de Ocupación» es ocupación de vía pública, no primera ocupación.

Reclasificar tras cambiar reglas: subir `REGLAS_VERSION`; la siguiente lectura de cada tablón rehace las clases no manuales.
