# Curtis — INE 15032, A Coruña (Galicia)

Comprobación en vivo: 2026-11-09. Adaptador exclusivamente de Curtis, sin licencias
concedidas, sin geocodificación y sin publicación automática.

## Fuentes oficiales y descubrimiento

El portal del Concello mantiene el inventario de Urbanismo → PXOM:
https://curtis.gal/index.php/es/urbanismo/pxom

Es un artículo Joomla, sin paginación en la captura revisada, que enumera cinco
referencias. Se descubrieron y recorrieron sus dos enlaces a detalles municipales:

- https://curtis.gal/index.php/es/129-avisos/3225-exposicion-publica-das-modificaciones-puntuais-n-6-e-n-7-do-pxom
- https://curtis.gal/index.php/es/noticias/5210-proyecto-de-reparcelacion-ape-4

La sede también ofrece el inventario de planes/programas:
https://sede.curtis.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
Su resultado público incluye PXOM y planes económicos/subvenciones; no se usa como
registro de obras ni de licencias. La búsqueda oficial también localizó el
inventario provincial de obras https://plan-unico.dacoruna.gal/curtis/ ; queda fuera
de este adaptador, que cubre únicamente los documentos urbanísticos municipales.
No se presenta una búsqueda de noticias o de contratación como un registro completo.

## Registros extraídos y agrupación

La ejecución real produce **3 instrumentos**, con **9 enlaces PDF**:

- Modificación puntual nº 6 del PXOM, delimitación de núcleos rurales: anuncio DOG,
  planos y modelo de alegaciones (3 documentos).
- Modificación puntual nº 7 del PXOM, categorías de suelo rústico: anuncio DOG,
  planos y modelo de alegaciones (3 documentos).
- Proyecto de reparcelación APE-4: tres tomos del proyecto (3 documentos).

Las modificaciones comparten una página, pero constituyen instrumentos distintos:
se agrupan por encabezamiento y lista contigua. El modelo de alegaciones de la MP7
está alojado en el directorio MPN6; no se agrupa por carpeta. Los modelos son
solamente documentos auxiliares del instrumento, nunca licencias ni proyectos
independientes. APE-4 tiene un enlace rotulado «Tomo 4» cuyo fichero se llama
`Proy_Reparc_APE4_Tomo_3.pdf`: se conservan tanto el rótulo como la URL, sin corregir
ni inventar un tomo faltante.

Se verificaron los nueve enlaces con GET Range (bytes 0–1023): HTTP 206,
`application/pdf` y firma `%PDF-`. Esta comprobación acredita accesibilidad de los
PDF, no revisión jurídica del contenido ni descarga íntegra de los tomos.

## Cobertura parcial y fechas

El inventario enlaza documentación histórica y actual: no equivale a una relación
certificada de planeamiento vigente. El título del aviso de MP6/MP7 indica que la
exposición terminó el 28 de mayo, sin año explícito en el cuerpo. APE-4 no indica
fecha ni fase de aprobación en el artículo. No se usan carpetas 2015/2026, nombres
de fichero, metadatos HTTP ni el día de ejecución como fechas administrativas.
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas; tampoco se deduce
una fase de aprobación del tipo del instrumento. La fecha de extracción consta
separadamente en la validación.

Se conservan en `excluded_references` del informe las otras tres referencias:

- PXOM: enlace genérico al inventario regional SIOTUGA, sin identificador municipal
  en la URL. La narrativa municipal menciona aprobación en 2007; no se inventa una
  fecha exacta ni se considera ese resumen una descarga del expediente completo.
- Convenios urbanísticos: referencia regional no desglosada ni revisada por convenio.
- «Modificación del Plan Parcial»: enlace ZIP regional cuyo nombre es
  `CURTIS_MP_PXOM_N2_25.09.25.zip`. Hay discordancia entre rótulo y nombre; no se
  afirma identidad, fecha ni aprobación sin examinar el expediente regional.

Estas referencias no se siguen ni se convierten en registros. La cobertura se
limita explícitamente a las páginas documentadas municipales enlazadas por PXOM,
no a todo SIOTUGA, obras provinciales, noticias, contratos o licencias. Una forma
de solicitud o anuncio de licitación nunca se interpreta como licencia concedida.

## Geometría y comportamiento

geometry_status: unavailable

Las páginas leídas aportan planos PDF y tomos, sin coordenadas o geometría vectorial
vinculada al identificador de cada instrumento. No se ha validado una capa de visor
ni vectorizado planos. Latitud, longitud y geometría quedan nulas;
`publication_ready` es falso. `geocode.jitter_missing: false`,
`schedule.enabled: false`, `licencias.enabled: false`.

El adaptador descubre detalles desde el inventario en cada ejecución y actualiza
por instantánea completa, sin cursor temporal. Deduplica enlaces y mantiene IDs
semánticos por número de instrumento. Rechaza paginación detectada, páginas sin
contenido, instrumentos sin PDF y PDF de modificaciones que no se puedan asignar
a un encabezamiento; así no se acepta silenciosamente una página truncada o
incompatible. Escribe el resultado solamente tras completar todas las páginas.

## Validación y reproducción local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_curtis -v` — **7 pruebas, todas pasan**.
Cubren agrupación de MP6/MP7 y tomos, formularios auxiliares, fechas no inferidas,
paginación, cambios de estructura/documentos ausentes, actualización atómica,
manifiesto/carga dinámica y licencias deshabilitadas.

Extracción real mediante `load_manifest('curtis')`, `load_portal_adapter(manifest)`
y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Para guardar las
páginas descargadas se estableció `manifest.portal.config['capture_dir']` en
`evidence/captures`. El cargador aplica además la política de entidades existente:
los tres instrumentos quedan `unknown` (categorización, no rechazo), sin fabricar
una categoría de inmueble.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML en `evidence/captures/` y capturas de
investigación en `evidence/`. La validación conserva recuento real, URL de inventario
y detalles, exclusiones, limitaciones y comprobaciones de los nueve documentos.
