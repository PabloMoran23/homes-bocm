# La Algaba (Sevilla), INE 41007

Consulta y extracción real: 7 de noviembre de 2026. Adaptador de inventario
documental oficial, con cobertura municipal parcial y licencias desactivadas.

## Descubrimiento oficial y alcance

La [web municipal de transparencia](https://www.laalgaba.es/es/ayuntamiento/transparencia/)
enlaza al [portal de la sede electrónica](https://laalgaba.sedelectronica.es/transparency).
Su sección [7. Urbanismo, obras públicas y medio ambiente](https://laalgaba.sedelectronica.es/transparency/be2fda89-f594-4a3f-8f85-6b614977f4d5/)
indica 78 documentos; [7.1. Planeamiento urbanístico](https://laalgaba.sedelectronica.es/transparency/c4ef4091-d187-42cb-93df-090ae8c560f8/)
indica 68. Son contadores documentales, no números de proyectos. Las carpetas
se descubrieron siguiendo las acciones públicas Wicket de navegación: la
respuesta `Ajax-Location` proporciona las URL estables de carpeta.

**Fuente extraída:** [carpeta PGOU](https://laalgaba.sedelectronica.es/transparency/5985c8b3-4e2b-44ac-be3d-bd5515df4147/).
Se lee su tabla `TransparencyListPanel` y se verifica la ruta visible
`PLANEAMIENTO URBANÍSTICO/PGOU`. La extracción en vivo produjo **dos instrumentos
con cinco documentos**, conservando cada título documental, enlace de vista
previa e inventario de procedencia:

| Instrumento | Documentos publicados en la carpeta |
| --- | --- |
| Plan General de Ordenación Urbanística | NORMAS_URBANISTICAS; Planos PGOU; MEMORIA GENERAL |
| Reformado de la Modificación Puntual n.º 3 del PGOU | Documento de Reformado de Modificacion Puntual del PGOU nº 3.Diligenciado; Documento Reformado de Modificación Puntual nº 3 del PGOU |

La agrupación del plan usa los nombres documentales explícitos dentro de su
carpeta. La de modificaciones usa el número del instrumento y la mención a
su reformado, conservando ambas versiones publicadas. No se crean actuaciones
separadas para normas, planos, memoria o versión diligenciada. Se conservan los
enlaces `preview-document` estables, en lugar de fijar tokens de descarga efímeros.

## Cobertura parcial y fuentes excluidas

El resto del árbol no forma parte del inventario extraído. La sección superior
de Planeamiento tiene documentos sueltos y un control «Mostrar más»; no se
presenta su primera página como un inventario completo. La subcarpeta
[Plan Especial de Infraestructuras](https://laalgaba.sedelectronica.es/transparency/42bd3f01-e1f6-4777-bfd6-49bc497a1630/)
tiene 17 documentos, incluyendo subcarpetas ambientales e informes sectoriales;
no se ha implementado su recorrido. Tampoco se extrae el
[tablón oficial](https://laalgaba.sedelectronica.es/board), que muestra un anuncio
del Plan Parcial SI-3, expediente 30/2020, publicado el 05/11/2026. Esta es una
fecha de publicación del anuncio, no una fecha de aprobación deducible del listado.
El tablón también tiene «Mostrar más» y no se ha recorrido íntegramente.

La [página municipal de trámites](https://www.laalgaba.es/es/ayuntamiento/servicio-de-atencion-al-ciudadano/tramites/)
contiene solicitudes y autoliquidaciones: no son licencias concedidas. No se
convierten formularios, anuncios de contratación, empleo, ordenanzas ni noticias
en proyectos. `licencias.enabled=false` porque no se ha verificado un registro
público de concesiones. Los métodos de licencias generan cero registros.

La carpeta PGOU revisada contiene los cinco documentos en una sola página y
no muestra «Mostrar más». El adaptador aborta ante controles de paginación,
subcarpetas, documentos desconocidos, respuestas vacías, cambios de carpeta
o redirecciones inesperadas. Así no sustituye una extracción previa por otra
silenciosamente incompleta. Un cambio de estructura requiere revisión; este
adaptador no afirma soportar la paginación del resto de la sede.

## Fechas, estado y geometría

No se interpretan los PDF para extraer acuerdos ni se asignan fechas de
aprobación, publicación o vigencia a estos instrumentos. La vista del reformado
diligenciado muestra «Fecha de creación 22-may-2026 13:46:51»: es metadato del
documento de la sede, no prueba de aprobación ni publicación. Se omiten esos
campos y `fase`. No se deducen coordenadas ni parcelas. Los registros declaran
`geometry_status=unavailable`, `publication_ready=false` y cobertura parcial.
El manifiesto desactiva ejecución programada y jitter de geocodificación.

## Verificación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_la_algaba -v`: **7 correctas**. Comprueban
agrupación y conservación de documentos, aislamiento entre modificaciones,
ausencia de fechas/geometría inventadas, rechazo de documentos impropios,
paginación, carpeta incorrecta y respuesta vacía, manifiesto y conservación de
la salida previa ante fallo.

Ejecución real mediante `load_manifest('la-algaba')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura local de la
respuesta configurada en `capture_dir`. Se aplicó también la anotación de
entidades normal del registro de adaptadores. No se usaron bases de datos,
geocodificación, publicación ni comandos del pipeline completo.
La política compartida devuelve `unknown=2` para su clasificación de entidades;
no se han cambiado sus reglas ni se afirma que estos instrumentos estén listos
para publicación.

Evidencia local, fuera de los cuatro archivos fuente:

- `evidence/proyectos.jsonl`: dos registros realmente extraídos.
- `evidence/validation.json`: contador, URL fuente, limitaciones, resultado del
  adaptador, comprobaciones documentales y SHA-256 del inventario capturado.
- `evidence/pgou-live.html`: respuesta usada por el adaptador.
- Capturas de descubrimiento y cinco páginas `preview-*.html`.
- Cinco muestras `pdf-prefix-*.bin`: HTTP 200 y firma `%PDF-` verificada en los
  primeros 512 bytes de cada documento enlazado. No se descargaron ni
  interpretaron íntegramente los PDF. La comprobación de enlaces es evidencia
  de esta ejecución, no una afirmación sobre su disponibilidad futura.
  Los PDF temporales requieren la sesión de su vista previa; los registros
  conservan los enlaces estables de documento.
