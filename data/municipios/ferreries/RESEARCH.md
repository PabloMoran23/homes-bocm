# Ferreries — INE 07023, Illes Balears

Revisión y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y cobertura

Se revisaron `municipio/adapters/portal.py`, el cargador de manifiestos y los
adaptadores/manifiestos de Manlleu y Hernani antes de implementar.

La [web oficial](https://www.ajferreries.org/) enlaza las secciones del PGOU desde
«Urbanisme i governació». El [índice de transparencia](https://www.ajferreries.org/Contingut.aspx?IdPub=2806)
enlaza el [apartado E de urbanismo y obras](https://www.ajferreries.org/contingut.aspx?idpub=2811),
que identifica el [inventario PGOU](https://www.ajferreries.org/Contingut.aspx?IdPub=99).
Este último es la semilla del adaptador, no un PDF aislado ni una noticia fijada.
Su contenido enumera cinco secciones que se descubren y recorren en cada ejecución:

- [ISA](https://www.ajferreries.org/Contingut.aspx?IdPub=60): documentación ambiental.
- [Normativa](https://www.ajferreries.org/Contingut.aspx?IdPub=61): normas, rectificación y cartografía.
- [Memoria justificativa](https://www.ajferreries.org/Contingut.aspx?IdPub=62).
- [Memoria informativa](https://www.ajferreries.org/Contingut.aspx?IdPub=63).
- [Memoria de gestión](https://www.ajferreries.org/Contingut.aspx?IdPub=64).

Resultado en vivo: **1 instrumento de planeamiento con 75 URLs documentales**.
La normativa descargada confirma en portada «REVISIÓ DEL PGOU I ADAPTACIÓ AL PLA
TERRITORIAL INSULAR / TEXT REFÓS / NORMES URBANÍSTIQUES», diciembre de 2012.
Es un instrumento real; el inventario conserva versiones de años distintos y
rectificaciones. No acredita por sí solo una versión jurídica consolidada vigente.
Cada enlace conserva título, sección y página de procedencia; los repetidos por URL
se agrupan conservando todas sus procedencias. Los planos y memorias no generan
proyectos adicionales. No se inventan enlaces para rótulos sin href: el HTML de la
memoria informativa contiene rótulos cartográficos fusionados por marcado defectuoso.

Cobertura deliberadamente parcial: únicamente ese inventario documental. El apartado
E también enlaza PAESC, perfil del contratante y noticias de urbanismo; no se extraen
como expedientes de obras. No se afirma cubrir todas las modificaciones, instrumentos
de desarrollo, obras municipales o un histórico de licencias. La
[Carpeta Ciutadana](https://nova.carpetaciutadana.org/ferreries/Portal.aspx) y el
[trámite de licencia](https://carpetaciutadana.org/ferreries/gesserveis/Gestion.aspx?IDGESTION=32)
son canales de tramitación; un formulario no prueba una concesión. Licencias deshabilitadas.

## Fechas y procedencia documental

Las fechas y fase del instrumento quedan nulas. No se infiere aprobación de «ap»,
«TR2012», año de carpeta o fecha de documento. Los títulos se conservan como fuente,
sin convertir su contenido en fechas estructuradas del PGOU completo.

Caso comprobado: el enlace de normativa llama a la rectificación «BOIB núm 6 en data
de 12 de maig del 2026». El [PDF municipal 4566](https://www.ajferreries.org/WebEditor/Pagines/File/4566.pdf)
indica realmente **núm. 60, 12 de mayo de 2026**. Describe un acuerdo provisional del
27 de febrero de 2025, publicado el 11 de marzo de 2025, que devino definitivo sin
nuevo acuerdo expreso. Esas fechas pertenecen a esa rectificación, no a la aprobación
del PGOU. Se conserva el enlace y rótulo municipal sin atribuir al instrumento ninguna
de esas fechas. PDF y texto extraído se guardaron en evidencia local.

## Paginación, actualización y geometría

Las seis páginas del inventario son listas sin paginación observada. Se procesan
todos los enlaces de contenido de cada sección, incluidos PDFs sin rótulo y RAR;
no hay límite de número de registros ni recorte de resultados. Si aparece navegación
«siguiente», `rel=next`, una sección incompleta, enlaces no soportados o contenedores
ausentes, se falla sin reemplazar una salida previa válida. Los límites de tamaño de
respuesta también fallan explícitamente, nunca devuelven contenido recortado.
`update_proyectos` refresca la instantánea completa; no se simula un cursor incremental.

La cartografía disponible está enlazada en PDF. No se ha verificado una geometría
vectorial asociada al instrumento, ni se han vectorizado planos o asignado centroides.
`lat`, `lon` y `geometry` son nulos; `publication_ready=false`.
`schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible

`python -m unittest municipio.test_ferreries -v`: **4 pruebas pasan**. Verifican
inventario completo, exclusión de enlaces de navegación, procedencias, agrupación y
deduplicación, ausencia de fechas/coordenadas inferidas, rechazo de paginación,
preservación de salida ante fallo, licencias deshabilitadas y carga por manifiesto.

Se ejecutó realmente `load_portal_adapter(load_manifest('ferreries')).backfill_proyectos`
con captura de HTML activada mediante `config.capture_dir`. El cargador aplica la
política compartida existente; clasifica este inventario sin expediente como
`unknown` y sin elegibilidad de actividad. No se inventa un número de expediente
para modificar esa clasificación.

Evidencia local, excluida del commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, seis capturas de ejecución en `evidence/live/`, páginas de
descubrimiento y los PDFs/textos de normativa y rectificación. Los otros documentos
se retienen como enlaces: no se han descargado ni validado todos sus contenidos.
No se modificaron fuentes compartidas ni dependencias ni se ejecutó publicación.
