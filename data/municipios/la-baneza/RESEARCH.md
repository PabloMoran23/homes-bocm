# La Bañeza — INE 24010, León

Verificado el 2026-11-07 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se implementa un único adaptador y una cobertura deliberadamente parcial:
un instrumento PGOU publicado en el inventario municipal actual, con cuatro
enlaces documentales agrupados. No es un inventario completo de obras ni un
registro de licencias concedidas. `schedule.enabled`, `licencias.enabled` y
`geocode.jitter_missing` son false; `publication_ready` es false.

## Descubrimiento y procedencia

Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro
de adaptadores y los ejemplos de Manlleu, Chipiona y Hernani antes de implementar.
El adaptador se carga por la ruta del manifest, sin modificar el registro compartido.

- [Navegación municipal: normativa urbanística](https://www.aytobaneza.es/ayuntamiento/Normativa_Urbanismo)
  redirige (resultado final HTTP 200) a
  [7.3. Normativa urbanística en la sede](https://aytobaneza.sedelectronica.es/transparency/f5fc0e43-eda2-4d84-98c9-d5608595b9d3/).
  La tabla pública `TransparencyListPanel` contiene un documento llamado
  «Plan General de Ordenacion Urbana». No presenta paginación en la captura.
  Ésta es la fuente actual principal, no una búsqueda de noticias.
- [Detalle público del documento PGOU](https://aytobaneza.sedelectronica.es/preview-document/0d59955b-b395-4a91-a6d7-d68a94527490)
  responde HTTP 200, identifica el documento y el formato PDF. Su fecha de creación
  mostrada es 25-mar-2020 11:04:48: es metadato del documento de la sede, no una
  aprobación ni una publicación del instrumento. No se reutiliza como tal.
- [Índice municipal conservado](https://www.aytobaneza.es/ayuntamiento/normativa-municipal/urbanismo/index.html)
  responde HTTP 200 y describe el mismo PGOU de La Bañeza (León), con tres enlaces
  complementarios. Se conservan los dos anuncios y la colección documental,
  junto con el documento de la sede, en una sola entidad `la-baneza-pgou`.
- [BOCYL de 12/02/2014](https://bocyl.jcyl.es/boletines/2014/02/12/pdf/BOCYL-D-12022014-45.pdf)
  responde HTTP 200. Anuncio del nuevo período de exposición pública por cambios
  sustanciales. La publicación es 2014-02-12; las sesiones plenarias de 2013-11-28
  y 2014-01-30 que se mencionan son acuerdos distintos, no esa publicación.
- [BOCYL de 08/03/2016](https://bocyl.jcyl.es/boletines/2016/03/08/pdf/BOCYL-D-08032016-8.pdf)
  responde HTTP 200. La primera página acredita el acuerdo de 2015-02-26 de la
  Comisión Territorial de Medio Ambiente y Urbanismo de León, expediente
  790/2012, para la aprobación definitiva del PGOU. La publicación es
  2016-03-08, no 2015-02-26. El PDF completo descargado ocupa 163.204.819 bytes.
  Se inspeccionaron las tres primeras páginas con `pdftotext`; no se afirma
  haber analizado todos los planos ni todas las condiciones del documento.
  La alternativa HTML `.do` probada devolvió HTTP 500 y no se usa como fuente.
- [Colección enlazada por el Ayuntamiento](https://drive.google.com/open?id=0B4QyXSg_pD1-UmdsUDlyVEdlNzg)
  responde HTTP 200 y se titula «2016 - P.G.O.U. DE LA BAÑEZA». Expone carpetas
  PLANOS, PLANOS INFORMACION, TEXTOS y una memoria. Se conserva el enlace a la
  colección con procedencia municipal, sin afirmar un inventario recursivo ni
  completitud de los archivos internos.

## Fuentes descartadas y límites

[Navegación de expedientes en exposición](https://www.aytobaneza.es/ayuntamiento/Expedientes_Exposicixn_Pxblica)
redirige a [7.1. Planeamiento urbanístico / En exposición pública](https://aytobaneza.sedelectronica.es/transparency/7d67d7fa-f77f-4e82-9fcc-d1617d1610c7/),
HTTP 200. En la captura aparecen carpetas PROSANDIMAS S.A., EXPEDIENTE 158/2022,
EXPEDIENTE 2275/2021 y una estación de recarga en Hotel-Restaurante La Hacienda,
con contador 0. No se convierten esos rótulos en proyectos aprobados ni licencias:
falta documentación verificable en esa respuesta.

El [tablón](https://aytobaneza.sedelectronica.es/board) y el
[portal general](https://aytobaneza.sedelectronica.es/transparency) responden
HTTP 200. El tablón mezcla empleo, bandos, consumo y contratación, por lo que no
se ingiere como inventario de proyectos. Tampoco se afirma haber recorrido todo
su histórico. Las [solicitudes municipales](https://www.aytobaneza.es/ayuntamiento/tramites-solicitudes/)
son trámites/formularios: no prueban concesiones. Las noticias de terceros no son
fuente del adaptador. No se accedió a áreas autenticadas.

## Semántica y funcionamiento

La fase «aprobación definitiva» procede literalmente del índice municipal
archivado, con `fase_source_url`. Las fechas se extraen de los títulos de cada
anuncio como `documentos[].fecha_publicacion`. Las fechas generales del proyecto
(`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`) permanecen null:
no hay una única publicación para todos los documentos y el parser no procesa
el acuerdo dentro del PDF. Aunque la investigación verificó su fecha, no se
codifica como constante ni se infiere de la fecha del boletín. La descripción
retiene el texto de origen y no se reutiliza como fase.

El adaptador consulta tres páginas HTML: inventario, índice municipal y detalle
documental público. Conserva todos los enlaces documentales revisados, con su
`source_url`; actualizaciones refrescan la instantánea completa. Un enlace
nuevo ajeno al esquema revisado, falta de documentos, cambios de inventario,
paginación o falta de detalle público producen error antes de reemplazar la
salida. No hay límite de filas ni truncamiento de paginación. Las respuestas
HTML se limitan a 3 MB con error explícito y timeout de 40 segundos. Los enlaces
HTTP de BOCYL se normalizan a HTTPS, verificado durante la investigación.

No hay geometría ni coordenadas verificadas. No se usa un centroide municipal,
una parcela supuesta ni jitter. `lat`, `lon` y `geometry` son null. La colección
de planos es un vínculo documental y no se interpreta como geometría estructurada.

## Validación reproducible y evidencias locales

- `.../venv/bin/python -m unittest municipio.test_la_baneza -v`: 6 pruebas
  superadas. Cubren agrupación de documentos, fechas separadas, contenido de
  navegación/login/formularios, paginación, cambios de inventario, procedencia,
  ausencia de fecha, refresco, preservación de salida ante error y licencias
  desactivadas. Las pruebas usan HTML mínimo independiente de las capturas locales.
- Extracción HTTP real mediante `LaBanezaAyuntamientoAdapter.backfill_proyectos`,
  con `config={'capture_dir': 'evidence'}`: 1 registro, cuatro enlaces documentales.
- `evidence/proyectos.jsonl`: resultado real. `evidence/validation.json`:
  `live_records=1`, URLs consultadas, limitaciones y resultado de pruebas.
- `evidence/live_inventory.html`, `evidence/live_archive.html` y
  `evidence/live_pgou_detail.html`: respuestas de la ejecución del adaptador.
  Otras capturas de descubrimiento, PDFs y textos de primeras páginas quedan
  también en `evidence/`. Las evidencias son locales, fuera de los cuatro archivos
  fuente que forman esta entrega.

No se requieren dependencias nuevas. No se han ejecutado publicación,
sincronización, despliegue ni cambios de infraestructura.
