# Zumaia — INE 20081, Gipuzkoa

Investigación y extracción verificadas el 2026-11-07. Se inspeccionaron primero
`municipio/manifest.py`, el contrato `municipio/adapters/portal.py` y los ejemplos
Hernani y Manlleu. No se modifican contratos, registro compartido ni dependencias.

## Inventarios oficiales y selección

La página del [departamento municipal de Urbanismo](https://zumaia.eus/es/ayuntamiento/estructura-municipal/departamentos-1/urbanismo-servicios-y-medio-ambiente)
remite a documentos en exposición pública y normas subsidiarias.

Fuente implementada: [Documentos en exposición pública](https://zumaia.eus/es/ayuntamiento/documentos-en-exposicion-publica-1).
Es un inventario municipal de expedientes, no una búsqueda de noticias ni una
lista fija de proyectos. Sirve las dos pestañas completas en HTML: Abiertos (1),
Cerrados (26). Se recorren las 27 filas y se descubren los detalles por sus enlaces.
Los totales se contrastan contra las filas de cada pestaña; cualquier paginación,
total incompleto, detalle inconsistente o falta de documentos provoca un error.
No se aplica un límite temporal, de registros ni un corte de primera página.

Otros inventarios descubiertos, fuera de la cobertura de este adaptador:

- [Normas subsidiarias y planos](https://zumaia.eus/es/ayuntamiento/estructura-municipal/departamentos-1/urbanismo-servicios-y-medio-ambiente/normas-subsidiarias):
  catálogo de memoria, normativa, fichas y planos; enlaza el portal del nuevo PGOU.
  No se cuenta cada plano o ficha como un proyecto independiente.
- [Portal del PGOU](https://hapo-zumaia.eus/es): enlazado expresamente por el
  Ayuntamiento; la búsqueda pública describe el documento de aprobación inicial
  de 2024 y sus documentos. La apertura mediante navegador de investigación
  devolvió 403. No está incorporado a la extracción ni se deduce aprobación final.
- [Zumaia bizitzeko da](https://bizitzekoda.zumaia.eus/es/project_category/urbanismo-y-ordenacion-territorial/):
  inventario de medidas de mandato enlazado en la navegación municipal. Mezcla
  obras físicas, objetivos y otras políticas; no se incorpora como si todo fueran
  obras ejecutadas o instrumentos aprobados.

El tablón implementado sigue accesible pero sus filas observadas son de
2023–2024. Por ello esta es cobertura histórica parcial disponible actualmente,
**no un registro exhaustivo del planeamiento vigente en 2026**, ni de todas las
obras municipales. El PGOU más reciente no figura entre los seis instrumentos
extraídos. Las noticias de obras, los anuncios de contratación, los formularios y
las solicitudes de licencia no se utilizan como prueba de concesión.

## Registros y documentos

| Expediente | Instrumento | Publicación municipal | Documentos únicos |
| --- | --- | --- | --- |
| 2023HPXA0002 | Delimitación U.E. 4 del AU 04, aprobación inicial | 2024-01-02 | 2 |
| 2023HPXA0002 | Estudio de detalle AU 04 Arrangoleta, aprobación inicial | 2024-01-02 | 4 |
| 2023HPXA0001 | Estudio de detalle parcelas 1,2,3 UE 17/3, aprobación inicial | 2023-08-31 | 3 |
| 2021HPNS0003 | Modificación NNSS: alojamientos turísticos | 2023-05-16 | 8 |
| 2022KOFI0002 | Modificación artículo 67 NNSS: Aita Mari | 2023-02-10 | 3 |
| 2021HUUU0002 | Proyecto de urbanización del área de Torreaga | 2023-01-16 | 23 |

Se generan seis registros de instrumentos, con 43 documentos agrupados. Los dos
instrumentos de 2023HPXA0002 tienen detalles y proyectos distintos: se conserva
el expediente común, pero el ID estable deriva de la URL de cada instrumento.
Cada documento conserva título municipal, URL, página de procedencia y todos sus
enlaces. Las variantes Plone de vista y `@@download` se agrupan como un documento,
preferentemente con URL de descarga. Certificados, BOG, memorias, anexos y planos
no generan registros de proyecto adicionales. Se retienen enlaces a PDFs sin
extraer su contenido ni comprobar todas las descargas.

`fecha_publicacion` procede de la columna explícita Fecha publicación y se
contrasta con el detalle. No se usa Último día como fecha del proyecto. `fecha`,
`fecha_acuerdo` y `fecha_aprob` quedan nulas. El título sólo acredita la fase
«aprobación inicial» cuando la menciona expresamente; no se deducen fechas de
acuerdo de nombres de fichero, de publicaciones BOG ni de noticias. «Cerrados»
significa fin de exposición pública, no aprobación definitiva ni obra terminada.
No se extraen licencias: las solicitudes de ascensor no acreditan concesiones.

## Geometría y ejecución

Los detalles contienen planos PDF, incluido un anexo de cartografía y topografía
de Torreaga. No se ha verificado una geometría vectorial asociada por identificador
al instrumento. No se georreferencian imágenes ni se asigna el centro municipal.
`lat`, `lon` y `geometry` son nulos, `geometry_status: unavailable` y
`publication_ready: false`. `schedule.enabled: false`, `licencias.enabled: false`
y `geocode.jitter_missing: false`.

Backfill y actualización leen una instantánea completa. No se escribe el resultado
hasta haber validado todos los detalles, para preservar el fichero anterior ante
un fallo de red o de estructura. La actualización no usa una fecha de corte.

Validación con el Python preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_zumaia -v
```

Seis pruebas: selección semántica e identidad, documentos y alias, paginación y
totales, rechazo de detalles inconsistentes, instantáneas y preservación ante error,
y carga del manifest. La extracción real llama `backfill_proyectos` del adaptador
con `config.capture_dir=evidence`, sin orquestador, base de datos ni publicación.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json` y siete
capturas HTML. `validation.json` contiene recuento vivo, URLs y limitaciones.
