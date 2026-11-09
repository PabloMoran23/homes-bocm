# Andorra (Teruel), INE 44025

## Fuentes oficiales y alcance

Investigación y extracción real: 9 de noviembre de 2026.

El [portal de transparencia Andorra Abierta](https://andorraabierta.aytoandorra.es/home)
se identifica como servicio del Ayuntamiento de Andorra (Teruel). Su
[inventario de planeamiento PGOU](https://andorraabierta.aytoandorra.es/informacion-institucional/pgou)
expone documentos municipales concretos, no solicitudes de licencia ni noticias.
El contenido está servido por Google Sites: el título está dentro de `role=main`,
pero los párrafos documentales están en secciones posteriores fuera de ese nodo.
Se comprueban identidad, título y origen municipal de todos los PDF.

La extracción viva produce **3 instrumentos con 29 documentos únicos**:

- Plan General de Ordenación Urbana de Andorra (2007): 13 documentos, incluidas
  cuadrículas, planos de clases/usos del suelo y normas urbanísticas.
- Modificación 2 del PGOU, etiqueta fuente `Mod2(2008-07-30)`: 7 documentos,
  aprovechamiento medio, clases/usos, normas y cuatro paquetes de unidades de ejecución.
- Modificación puntual nº 4: 9 documentos, memoria justificativa, normas, índice de
  hojas de suelo no urbanizable y seis hojas cartográficas.

Los documentos se agrupan por contexto del párrafo y encabezado de instrumento;
los enlaces repetidos se deduplican dentro de cada instrumento. La referencia
`PGOU 2007` insertada en el párrafo del aprovechamiento de Mod2 apunta al plano
base de cuadrículas: se conserva en el plan base, sin atribuirlo a la modificación.
Cada documento conserva URL original, URL HTTPS, página inventario y etiquetas
completas de los párrafos donde se enlaza. No se extraen las unidades de ejecución
ni cada plano como proyectos independientes.

Los enlaces originales usan HTTP en `www.ayuntamientoandorra.es`. Se utiliza HTTPS
en ese mismo host para los documentos. Los **29** enlaces respondieron HTTP 200,
`application/pdf`, con firma `%PDF-` verificada leyendo solo un prefijo. Se guardan
los prefijos y resultados individuales en la evidencia. Dos muestras (normas del
plan y memoria de modificación 4) también se descargaron completas durante el
descubrimiento. La portada de `https://www.ayuntamientoandorra.es/` respondió 403;
esto no impidió el acceso a los documentos enlazados por el portal de transparencia.

## Semántica y límites

El inventario actualmente accesible contiene documentación histórica: no se afirma
que sea un texto consolidado vigente ni un registro completo de modificaciones.
Tampoco se pretende cubrir todas las obras públicas, expedientes o licencias.
No se convierten formularios, anuncios de contratación ni noticias en proyectos.
Licencias desactivadas por falta de registro público de concesiones verificado.

El año del plan y la fecha escrita en la etiqueta Mod2 son identificadores de
versión de la fuente; no establecen fecha de acuerdo, aprobación o publicación.
Los campos `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase`
quedan nulos. Las carpetas `/2016/05/` y `/2016/06/` de las URL tampoco se interpretan
como fechas del instrumento. No se ha extraído geometría de los PDF; coordenadas
nulas, `geometry_status: unavailable` y `publication_ready: false`.

Se recorren todos los párrafos del inventario, sin límite de registros. No se
observó paginación ni carga adicional; si aparece un control de siguiente página
o parámetro de paginación reconocido, el adaptador falla explícitamente. También
falla ante inventario vacío, identidad municipal inesperada, origen documental
ajeno o documentos que no pueda agrupar. Las actualizaciones refrescan la página
completa; no mantienen un historial de documentos retirados. La ejecución ordinaria
extrae enlaces, sin descargar todos los PDF ni verificar su contenido jurídico.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_andorra -v`: **5 correctas**. Cubren
agrupación, deduplicación, separación de documentos, fechas/geometría ausentes,
rechazo de fuentes vacías/ajenas o paginadas, snapshot y desactivación de licencias,
y carga del manifest.

Extracción viva mediante `load_manifest('andorra')`, `load_portal_adapter(manifest)`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local.
Se ejecutó también la política semántica compartida del cargador, sin modificarla.
Evidencia local excluida de control de versiones:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/pgou-inventory.html`,
capturas de descubrimiento, dos PDF completos y 29 prefijos documentales. El informe
registra `live_records: 3`, URLs, limitaciones y resultados HTTP. No se ejecutó ningún
paso de publicación, base de datos, despliegue o geocodificación. Manifest con
`schedule.enabled: false` y `geocode.jitter_missing: false`.
