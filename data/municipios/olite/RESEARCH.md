# Olite / Erriberri — Navarra, INE 31191

Verificado el 2026-11-09 con el runtime preinstalado. Adaptador exclusivo de este
municipio, sin cambios en fuentes compartidas ni dependencias.

## Descubrimiento y selección

La búsqueda de fuentes oficiales de urbanismo localizó estas páginas municipales:

- https://www.olite.es/general/transparencia/urbanismo-obras-publicas-y-medioambiente/
  responde HTTP 200, pero únicamente enumera categorías de información. No tiene
  enlaces a expedientes de obras o planeamiento; no se convierte en registros.
- https://www.olite.es/plan-general-municipal/ es el dossier oficial del nuevo PGM,
  con un inventario de secciones de participación y documentación. Explica que
  se pretende sustituir el plan actual y distingue EMOT y PUM. La mera explicación
  de estas fases no acredita su aprobación.
- El catálogo de sede electrónica localizado en la búsqueda contiene el trámite
  «URBANISMO - Licencia de obras», no un registro de concesiones. Se excluye.

El extractor parte del dossier, descubre sus cuatro secciones directamente
enlazadas y consulta todas, sin fijar una noticia como semilla:

1. https://www.olite.es/foro-1-sesion-informativa-plan-general-municipal/
   Publicación municipal 2023-08-22; enlaza la presentación del Foro 1.
2. https://www.olite.es/aportaciones-al-foro-1-y-cuestionario-estrategico-sobre-olite/
   Encuesta y participación. Conservada como contexto; la encuesta no es documento
   técnico ni genera otro proyecto.
3. https://www.olite.es/foro-2-sesion-informativa-plan-general-municipal/
   Publicación municipal 2024-05-24; contexto de presentación de la EMOT.
4. https://www.olite.es/exposicion-publica-emot/
   Inventario explícito «Documentación EMOT (Versión preliminar)»: memoria,
   evaluación ambiental, estudio de inundabilidad y cuatro conjuntos de planos.

## Semántica, documentos y límites

Resultado real: **un instrumento**, Plan General Municipal, con **ocho enlaces
documentales** agrupados. Las ocho URL son ficheros Google Drive enlazados por el
Ayuntamiento. Se conserva su título y página municipal de procedencia, sin afirmar
que Google Drive sea la administración editora. No se ha descargado ni validado el
contenido de esos ficheros; la evidencia acredita su publicación como enlaces en
la web oficial, no su accesibilidad futura.

Las páginas de los foros y la EMOT son documentación del mismo PGM, no proyectos
independientes. Los textos originales de cada página se conservan en
`paginas_fuente.texto_fuente`; las fechas visibles de los foros se guardan solamente
como `fecha_publicacion` de esas páginas. No se infieren fechas a partir del evento,
del directorio de subida o de metadatos de actualización. El dossier y la página
EMOT no muestran fecha de publicación; no se emiten fechas generales, de acuerdo,
de aprobación ni concesión. La EMOT se presenta como preliminar, sin acreditar
aprobación definitiva del PGM.

Cobertura parcial: exclusivamente el dossier PGM y las secciones directamente
enlazadas en su contenido. No incluye todo el planeamiento vigente, modificaciones,
actas, histórico de noticias o inventario de obras del municipio. Los enlaces de
navegación, redes sociales, imágenes, encuestas y noticias laterales se excluyen.
No hay paginación en las páginas consultadas; el extractor rechaza controles de
paginación o continuación, en vez de aceptar un inventario truncado. No recorre
recursivamente enlaces editoriales de las secciones. Una sección sin documentos,
como la encuesta, se conserva como contexto; un dossier sin ningún documento o
una respuesta sin contenido esperado provoca error y preserva la salida anterior.

`geometry_status: unavailable`: se publican enlaces a planos, sin capa vectorial o
geometría de instrumento verificada. No se han vectorizado planos ni asignado
coordenadas. `publication_ready: false` expresa esa limitación. La planificación
automática, las licencias y el jitter están deshabilitados en el manifest.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_olite -v`: cuatro pruebas pasan, cubriendo
agrupación documental, separación de fechas, exclusión de widgets/encuestas,
rechazo de paginación o fuentes incompletas, manifest y conservación de salida
ante fallo de red.

La extracción real se ejecutó mediante `load_manifest('olite')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, habilitando únicamente
`portal.config.capture_dir = 'evidence/live'` para guardar capturas locales.
Resultado: `live_records: 1`, ocho documentos, cinco páginas municipales consultadas.
La anotación compartida de entidades informa categoría desconocida para este PGM
general; no se fuerza una categoría de construcción.

Evidencias locales, no destinadas a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/live/*.html` y capturas de descubrimiento.
No se ejecutó publicación, sincronización, despliegue ni acceso a base de datos.
