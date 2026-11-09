# Nambroca — INE 45107, Toledo

Verificación en vivo: 2026-11-09. Un adaptador para el inventario documental
público de planeamiento del Ayuntamiento. Resultado: **4 instrumentos, 6 documentos**.
Cobertura parcial; no acredita vigencia jurídica, ejecución de obras ni licencias
concedidas. `schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`; registros con `publication_ready=false`.

## Descubrimiento oficial

- https://nambroca.com/ — HTTP 200; enlaza la sede electrónica y el tablón.
- https://nambroca.sedelectronica.es/transparency — HTTP 200; apartado
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (6)».
- https://nambroca.sedelectronica.es/transparency/4b86e787-a85e-43b6-accb-3c60707917bb/
  — HTTP 200; «7.1. PLANEAMIENTO URBANÍSTICO (6)». Los otros cuatro apartados
  (medio ambiente, normativa, obras e indicadores) muestran cero documentos.
- https://nambroca.sedelectronica.es/transparency/ac16ea95-0567-44b0-9da3-97b969d422bf/
  — HTTP 200; inventario utilizado, seis filas documentales, sin paginación.
  Los enlaces de carpetas usan Wicket AJAX y devuelven la dirección pública de
  carpeta en `Ajax-Location`; el adaptador usa directamente la URL estable de
  la carpeta verificada, sin sesiones autenticadas.
- https://nambroca.sedelectronica.es/board — HTTP 200; tablón general con
  «Mostrar más». Se excluye del alcance; su primera página no representa todo
  el tablón ni un registro de licencias. Formularios, anuncios de contratación,
  empleo y noticias no se convierten en proyectos.

## Instrumentos y documentos agrupados

1. PAU con Plan Parcial y Proyecto de Urbanización del sector 8B–8C:
   - https://nambroca.sedelectronica.es/preview-document/0b1d9e91-a4a9-466a-a804-6b463699a821
     — contenido normativo, BOP 2023-09-07.
   - https://nambroca.sedelectronica.es/preview-document/8c262953-cf56-4dd1-ba3c-3231aac4f29b
     — publicación DOCM 2023-05-02 sobre aprobación del PAU.
   Ambas publicaciones se agrupan en un expediente instrumental; no son dos
   obras. El PDF del BOP identifica expresamente el PAU, Plan Parcial y proyecto
   de urbanización. Las fechas explícitas en las etiquetas se guardan por
   documento. La lectura manual de ambos PDF confirma acuerdo plenario de
   2022-06-22, convenio de 2022-07-14 y registro de 2022-12-22. **El adaptador no
   extrae el texto PDF y no traslada estas fechas a los registros**. Tampoco
   confunde la fecha del anuncio (2023-04-18) con publicación ni acuerdo.
2. Proyecto de reparcelación del sector 8B–8C, revisión 2:
   - https://nambroca.sedelectronica.es/preview-document/f6fa9178-c897-430c-89ca-085a96f9e38b
     — portada verificada: revisión de mayo de 2023, vinculada al Plan Parcial.
     Es un instrumento de gestión distinto del PAU, no una segunda publicación
     del mismo. Mayo de 2023 no se transforma en fecha de aprobación.
3. Normas Subsidiarias y modificaciones: un registro para texto y planos:
   - https://nambroca.sedelectronica.es/preview-document/481eb198-1767-4b00-b272-472a74df3803
     — Planos NNSS.
   - https://nambroca.sedelectronica.es/preview-document/ca89628b-09e7-4850-a997-457ef41fc92a
     — TEXTO NNSS Y MODIFICACIONES NAMBROCA.
     No se desglosa el PDF compilatorio en supuestos expedientes individuales.
4. Modificación puntual de las NNSS para crear el nuevo sector 20:
   - https://nambroca.sedelectronica.es/preview-document/cf434a2b-203e-4e64-b140-9c15d82e7ee8
     — PDF BOP de 2026-01-15. Su texto identifica la modificación del nuevo
     sector 20 (antiguos 20, 21 y 23), aprobación inicial de 2006-10-30 y definitiva
     de 2007-06-25; explica la publicación tardía del contenido normativo. No es
     un proyecto nuevo aprobado en 2026. La etiqueta del inventario no muestra
     fechas; el adaptador mantiene todas sus fechas nulas.

Las seis páginas de previsualización devolvieron HTTP 200 y PDF accesible en
iframe. Se conservan sus URL públicas estables, sin incorporar las direcciones
opacas y temporales de descarga. `doc-0` a `doc-5` en evidencia corresponden al
orden de enlaces enumerado arriba. Los PDF son evidencia de identidad y
procedencia; no se realiza extracción de geometrías, parcelas, titulares ni
coordenadas. No se sustituye su localización por el centro del municipio.

## Comportamiento y límites

El adaptador descarga la carpeta completa (timeout 45 s, límite explícito de
2 MB que causa error, nunca recorte). Exige encabezado y tabla conocidos,
clasifica todas las filas y rechaza documentos desconocidos, enlaces externos,
grupos ausentes y controles de paginación. Cambios del inventario requieren
revisión; no se omiten filas desconocidas. Deduplica por URL dentro del instrumento
y utiliza identificadores estables por instrumento. La actualización refresca el
snapshot completo; no utiliza una marca temporal que pueda perder documentos.

Las seis entradas visibles coinciden con el contador de la carpeta padre en la
verificación. Esto sólo demuestra cobertura del inventario actual, no del archivo
histórico ni del tablón paginado. Las fechas genéricas, de acuerdo y aprobación
y la fase quedan nulas en todos los registros; sólo dos documentos tienen fecha
de publicación tomada de su etiqueta. La hora de la sede y «fecha de creación»
de los archivos no se usan como fechas de instrumentos.

## Validación reproducible

Runtime preinstalado, sin instalaciones ni cambios en fuentes compartidas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_nambroca -v
```

Cinco pruebas pasan: agrupación y fechas por documento, procedencia, rechazo de
contenido parcial o ajeno, paginación, identidad estable/deduplicación y contrato
manifest/actualización/licencias deshabilitadas. Extracción real mediante
`NambrocaAyuntamientoAdapter.backfill_proyectos`: estado `ok`, cuatro registros,
seis enlaces documentales. Configuración local `capture_dir=evidence` conserva
la respuesta usada en `planeamiento-live.html`.

`evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML, seis PDF y
extractos de comprobación permanecen locales y no forman parte de los cuatro
archivos fuente entregados. `validation.json` detalla fuentes y limitaciones.
