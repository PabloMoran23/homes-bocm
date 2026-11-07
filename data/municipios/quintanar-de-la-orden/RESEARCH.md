# Quintanar de la Orden — Toledo — INE 45142

Verificación: 2026-11-07. Un adaptador, exclusivamente para el inventario documental
municipal de planeamiento. Licencias y ejecución programada deshabilitadas;
`geocode.jitter_missing: false`.

## Descubrimiento y fuente oficial

La [portada municipal](https://www.quintanardelaorden.es/) enlaza «Normas
Urbanísticas» a https://www.quintanardelaorden.es/reglamento-urbanistico/.
Ambas responden HTTP 200; capturas locales `evidence/home.html` y
`evidence/reglamento-urbanistico.html`. La fuente es un índice de documentos,
no una noticia seleccionada ni un formulario. Sus dos apartados son «CONSULTA Y
DESCARGA DE TEXTOS» y «CONSULTA Y DESCARGA DE PLANOS».

Resultado real: **1 conjunto de planeamiento NNSS con 45 documentos únicos**
(7 textos y 38 planos). Se conserva cada título, URL, sección y página de
procedencia; se eliminan exclusivamente los botones «Descarga» duplicados.
Los planos rotulados «MP1» y «ZONIFICACIÓN mod NNSS1985» se mantienen dentro de la
colección municipal. No se inventan expedientes independientes para estas hojas,
ni se interpreta una previsión de saneamiento o abastecimiento como una obra en
ejecución. La identificación NNSS procede de la rotulación del índice; se descargó
y examinó también la memoria informativa oficial:
https://www.quintanardelaorden.es/wp-content/uploads/2020/08/02_-_MEMORIA_INFORMATIVA.pdf
(HTTP 200, PDF escaneado, captura `evidence/memoria-informativa.pdf`).

## Semántica y límites

Cobertura parcial: colección publicada actualmente, sin garantía de integridad
histórica, de vigencia jurídica o de todas las modificaciones posteriores. No es
un censo municipal completo de actuaciones, proyectos de obra ni concesiones.
No se utiliza la fecha del rastreo ni `/uploads/2020/08/` como fecha de publicación,
acuerdo o aprobación: todos esos campos quedan nulos, al igual que la fase.
Los años en etiquetas de planos se retienen literalmente sin convertirlos en
fechas de acuerdos. No hay número de expediente acreditado. La política compartida
del repositorio añade `entity_type: unknown`; se conserva este resultado sin forzar
su clasificación ni fabricar una referencia administrativa.

El [catálogo de sede electrónica](https://quintanardelaorden.sedelectronica.es/info.0)
expone solicitudes de licencias: no acredita concesiones y no se extrae como tales.
Los anuncios de licitación y noticias generales de portada quedan excluidos.

No hay paginación en el índice examinado. Se procesan todos los bloques de archivo
sin límites de registros. El adaptador falla explícitamente ante controles de
paginación o continuación, desaparición de las secciones, títulos obligatorios o
URLs documentales inesperadas; el límite de bytes también produce error, nunca una
respuesta truncada aceptada. Una actualización refresca la colección completa y
reemplaza atómicamente el JSONL sólo después de analizar la página correctamente.

## Geometría

`geometry_status: unavailable`. Los planos PDF se conservan como documentos, sin
vectorizarlos ni asignar un centroide municipal. No se ha acreditado geometría
vectorial por instrumento ni CRS; latitud, longitud y geometría quedan nulas y
`publication_ready: false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_quintanar_de_la_orden -v
```

Cuatro pruebas offline: agrupación y procedencia, ausencia de fechas/posición,
rechazo de fuentes/paginación no cubiertas, conservación de salida ante fallo de
red, licencias deshabilitadas y carga del manifest/adaptador.
Extracción real ejecutada mediante `load_portal_adapter(load_manifest(...))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir: evidence`
configurado sólo durante la validación local. El resultado y sus limitaciones están
en `evidence/validation.json`; los enlaces de los 45 documentos se conservan allí.
`evidence/document-checks.json` registra comprobaciones HTTP y cabeceras PDF por
enlace, sin afirmar revisión íntegra de todos los documentos. Evidencias locales
fuera de los cuatro archivos fuente; sin cambios compartidos ni dependencias.
