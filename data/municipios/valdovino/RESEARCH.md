# Valdoviño — INE 15087, A Coruña, Galicia

Investigación y extracción en vivo: 2026-11-09. Adaptador de cobertura deliberadamente
parcial: inventario documental municipal de delimitación de nuevos núcleos rurales.
Una modificación del planeamiento es un instrumento real, no una licencia, una
solicitud ni una noticia. Se agrupan sus diez documentos en una única fila.

## Descubrimiento oficial

- https://www.concellodevaldovino.com/urbanismo/ — índice municipal vigente,
  HTTP 200. Enlaza planeamiento general, planeamiento de desarrollo aprobado,
  información pública, trámites, oficina técnica, catastro y movilidad.
- https://www.concellodevaldovino.com/urbanismo/planeamento-xeral/ — HTTP 200.
  Enlaza normas subsidiarias (SIOTUGA), PXOM, delimitación y suelo industrial.
  El bloque paginado de últimas noticias no es el inventario documental.
- https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15087 —
  destino oficial de normas subsidiarias y desarrollo aprobado. La petición
  resuelve al buscador actual de inventario municipal, con selector de concellos;
  no devuelve las filas de Valdoviño en el HTML obtenido. No se declara extraído.
- https://www.concellodevaldovino.com/urbanismo/informacion-publica/ — HTTP 200;
  sección «Expedientes» con siete entradas «Próximante», sin documentos.
- https://www.concellodevaldovino.com/urbanismo/planeamento-xeral/ordenacion-municipal/
  — HTTP 200. Explica el PXOM en redacción desde 2020. No se convierte su texto
  general ni el enlace de convenios en nuevas filas del inventario seleccionado.
- https://www.concellodevaldovino.com/urbanismo/planeamento-xeral/solo-industrial/
  — HTTP 200. Describe As Boeiras, compartido con Narón y pendiente de desarrollar;
  no se considera una obra ejecutada ni una licencia concedida.
- https://www.concellodevaldovino.com/urbanismo/planeamento-xeral/delimitacion/
  — **fuente implementada**, HTTP 200. Incluye la modificación puntual núm. 14
  de las NNSSPP para delimitación de solo de núcleo rural y diez PDF agrupados
  bajo su propio encabezado. No se generan 37 proyectos por los núcleos citados.

## Documentos y fechas

La sección «Descargas» del instrumento enlaza:

1. Parte I: información — `informacion.pdf`.
2. Parte II: xustificación — `xustificacion.pdf`.
3. Análise do modelo de asentamento poboacional — `analise.pdf`.
4. Planos — `planos.pdf`.
5. Normas urbanísticas — `normas.pdf`.
6. Aprobación definitiva no BOP — `bop.pdf`.
7. Resolución no DOG — `dog.pdf`.
8. Fichas do catálogo de protección do patrimonio cultural — `fichas.pdf`.
9. Normas de protección do catálogo — `normas_0.pdf`.
10. Memoria do catálogo de protección do patrimonio cultural — `memoria.pdf`.

Todos bajo `https://www.concellodevaldovino.com/arquivo/sites/default/files/`.
Las URLs completas se conservan en `documentos`, con título y página de
procedencia. Los diez enlaces respondieron HTTP 200, `application/pdf`, mediante
HEAD. BOP y DOG se descargaron y se inspeccionaron con `pdftotext` local:

- [DOG municipalmente alojado](https://www.concellodevaldovino.com/arquivo/sites/default/files/dog.pdf):
  DOG núm. 240, publicación **2025-12-12**; resolución **2025-12-01** que hace
  pública la orden de aprobación definitiva de **2025-11-24**.
- [BOP municipalmente alojado](https://www.concellodevaldovino.com/arquivo/sites/default/files/bop.pdf):
  BOP núm. 7, publicación de normativa **2026-01-13**, anuncio 2026/65.
  Reitera la aprobación **2025-11-24** y cita expediente TEDEC 2021/X999/000466.
  El anuncio está fechado **2026-01-08**, fecha distinta de la publicación.

Estas son comprobaciones de investigación, no constantes insertadas en registros.
El adaptador no interpreta PDF: `fecha`, `fecha_publicacion`, `fecha_acuerdo`,
`fecha_aprob` y `fase` quedan nulos. No usa la fecha de noticias, descarga o
actualización como fecha del instrumento. Los boletines acreditan que se trata
de planeamiento real; no se ha auditado la consistencia de versión de los otros
ocho PDF. No se atribuye al alojamiento municipal la autoría de los boletines.

## Contrato y límites

- Lectura íntegra de la página específica; identifica los encabezados documentales
  de modificaciones y retiene todas sus URL, sin límite de registros o documentos.
  La sección documental no tiene paginación. Una navegación «siguiente» dentro
  de ella produce error; la paginación del widget de noticias queda fuera.
- Identidad estable por número de modificación de las NNSS de Valdoviño, no por
  orden de documentos ni fecha de extracción. Documentos repetidos se deduplican.
- Fallo explícito ante página sin encabezado, instrumento sin documentos, enlaces
  inesperados, duplicados ambiguos o redirección. Escritura atómica tras parsear;
  un error no sustituye la extracción anterior. Actualización = snapshot completo.
- No cubre todo el planeamiento municipal, otros proyectos ni obras públicas.
  Tampoco afirma cubrir todas las modificaciones NNSS: únicamente las mostradas
  en la página municipal de delimitación. El buscador SIOTUGA requiere otro trabajo.
- No se ha verificado registro público de licencias concedidas. Los enlaces a
  procedimientos de solicitud no son concesiones; `licencias.enabled: false`.
- Sin geometría extraída: `lat`, `lon`, `geometry` nulos y `publication_ready: false`.
  Los planos PDF permanecen enlazados, sin inventar centroides o coordenadas.
  `geocode.jitter_missing: false` y `schedule.enabled: false`.
- La anotación compartida de categorías informa `unknown` para esta denominación
  gallega; se conserva el título original y el tipo documental sin falsear categorías.

## Verificación reproducible

Runtime solicitado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_valdovino -v`

Resultado: seis pruebas correctas: agrupación y fechas nulas, documentos duplicados,
rechazo de páginas vacías o solicitudes, paginación documental/enlaces inesperados,
carga desde manifest con actualización idempotente/licencias deshabilitadas y
conservación de la salida previa ante contenido inválido.

Ejecución real mediante `load_manifest('valdovino')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 10 documentos**.
La opción local `capture_dir` guarda la respuesta realmente usada en esa ejecución.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live-delimitacion.html`, capturas HTML de
los índices y secciones investigados, `document_checks.json`, `dog.pdf`, `bop.pdf`
y sus textos. No se cambian dependencias ni fuentes compartidas; no se ejecutan
publicación, despliegues, base de datos ni operaciones Git de escritura.
