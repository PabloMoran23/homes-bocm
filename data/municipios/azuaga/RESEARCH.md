# Azuaga — INE 06014, Badajoz, Extremadura

Verificado el 2026-11-08 con el runtime preinstalado. Adaptador único:
`municipio.adapters.azuaga:AzuagaAyuntamientoAdapter`.

## Descubrimiento y cobertura

La portada oficial https://azuaga.es/ enlaza «Ayuntamiento → Normativa y
Solicitudes»: https://azuaga.es/plantilla.php?enlace=normativa (HTTP 200).
Es un inventario documental municipal actual, no una noticia individual elegida
como semilla. La sección `.contenidop` enumera las Normas Subsidiarias junto a
ordenanzas fiscales, formularios y otros documentos. El adaptador descubre las
URLs por el título de las entradas del inventario, sin fijar nombres de archivo.
Solo cubre la familia documental de las Normas Subsidiarias de Azuaga.

Resultado real: **1 instrumento de planeamiento, 2 documentos**, agrupados con
ID estable `azuaga-proy-normas-subsidiarias`:

- «Planos Normas Subsidiarias de Azuaga»:
  https://azuaga.es/documentos/20190321080135.zip — HTTP 200,
  11.882.967 bytes. Contiene `planos_nnss_azuaga.pdf`.
  Fecha de Alta municipal: 2019-03-21.
- «Normas Subsidiarias»:
  https://azuaga.es/documentos/20230614083632.pdf — HTTP 200,
  6.915.871 bytes. PDF escaneado; la primera página inspeccionada muestra el
  índice de información urbanística. Fecha de Alta municipal: 2023-06-14.

Las fechas se conservan como `documentos[].fecha_alta`. **No son fechas de
acuerdo, aprobación ni publicación de un anuncio legal**. Los campos
`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan
nulos: este inventario no acredita esos hechos ni la vigencia legal consolidada.
Se conserva también el enlace municipal a
https://sitex.juntaex.es/SITEX/planeamiento, identificado como portal autonómico
general, sin atribuirle un expediente específico. Se consultó su página HTTP 200;
no se incorpora su catálogo completo ni se usa como otro instrumento.

## Fuentes alternativas y exclusiones

Se revisaron y capturaron la portada, Normativa, la página de la concejalía
`plantilla.php?enlace=industria_urbanismo`, Transparencia, `tablon.php` y `bop.php`.
La página de concejalía no contiene un inventario de proyectos. Transparencia
remite a otro portal; no se ha extraído un inventario completo de ese servicio.
El tablón tiene paginación (12 páginas en la consulta); **no se ha recorrido ni
se reclama cobertura de su histórico**. BOP mezcla anuncios de personal,
presupuestos, solicitudes de apertura y otras materias; no se convierten en
proyectos ni licencias. La sede pública también aparece en el descubrimiento
web, sin reclamar extracción de su tablón o de expedientes privados.

Los formularios «Solicitud licencia obra mayor», «Solicitud comunicación previa
obra menor» y «Solicitud de licencia primera ocupación» son solicitudes vacías,
no concesiones. No hay registro de licencias concedidas verificado en este trabajo.
`licencias.enabled: false`; los métodos correspondientes producen cero filas.
No se extraen anuncios de contratación, planes de subvenciones ni noticias.

La cobertura es parcial y documental: no incluye todas las modificaciones,
planeamiento histórico, obras públicas ni seguimiento administrativo. Un PDF y
un ZIP asociados al mismo instrumento nunca producen dos proyectos.

## Paginación, fallos y geometría

El inventario Normativa revisado no tiene paginación. El adaptador inspecciona
toda su sección sin límite de filas y rechaza enlaces de paginación reconocibles
si aparecen, hasta revisar su recorrido. Rechaza pérdida de sección, falta de
normativa o planos, ubicaciones inesperadas y documentos que no sean PDF/ZIP.
Límites de tamaño de respuesta producen error explícito, nunca truncamiento.
La salida se reemplaza solo después de descargar y validar ambos documentos.
Los documentos conservan procedencia, tamaño, SHA-256 y, para ZIP, sus miembros.
Las actualizaciones vuelven a consultar el inventario completo, sin cursor ficticio.

`geometry_status: unavailable`. El material verificado es PDF escaneado y planos
PDF dentro de ZIP, sin geometría vectorial asociada ni CRS verificable. El enlace
municipal a SITEX es general, sin identificador espacial del instrumento. No se
vectoriza ni se inventan coordenadas. `publication_ready: false`,
`geocode.jitter_missing: false`, `schedule.enabled: false`.

## Validación reproducible

Desde la raíz, usando exclusivamente el entorno preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_azuaga -v
```

Cuatro pruebas pasan: agrupación/deduplicación, exclusión de formularios y fechas;
rechazo de contenido incompleto, paginación, URL externa y fecha inválida;
preservación de salida ante descarga inválida; carga del manifest y licencias
vacías. Los fixtures son sintéticos y no se utilizan como extracción en vivo.

Se ejecutó además `load_manifest('azuaga')`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir'] = 'evidence'`. Resultado: **1 fila real**.
La anotación compartida de entidades devuelve `pendiente` por identidad
insuficiente para actividad; no demuestra una obra ni una licencia concedida.
No se altera esa política. El instrumento documental sigue siendo verificable.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/inventory.html`, PDF y ZIP descargados,
capturas de descubrimiento y vista de la primera página del PDF. Validation
incluye `live_records`, `source_urls`, limitaciones y resultado del adaptador.
