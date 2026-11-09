# Las Navas del Marqués — investigación y cobertura

Verificado el 9 de noviembre de 2026. Municipio INE **05168**, provincia de
**Ávila**, Castilla y León. Un único adaptador, sin cambios compartidos ni nuevas
dependencias. Ejecución programada, licencias y jitter desactivados.

## Fuentes oficiales descubiertas

- [Área municipal de Obras, Urbanismo y Servicios](https://lasnavasdelmarques.es/areas/obras-urbanismo-y-servicios):
  índice de servicios y antiguas aprobaciones iniciales (modificaciones 16 y 17).
  Las páginas «Licencia de Obra Mayor/Menor», primera ocupación y apertura
  explican solicitudes; no acreditan licencias concedidas y se excluyen.
- [Normativa Urbanística municipal](https://lasnavasdelmarques.es/areas/obras-urbanismo-y-servicios/normativa-urbanistica):
  enlaza expresamente al archivo de la Junta para provincia 05, municipio 168.
  Se comprobó el enlace mediante navegación web. Las peticiones Python a la web
  municipal y sus variantes www/ipv4 devolvieron HTTP 403; el adaptador no depende
  de una copia indexada de esas páginas.
- [Archivo de Planeamiento Urbanístico y Ordenación del Territorio de JCyL](https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=168):
  fuente efectiva en vivo, HTTP 200. Cabecera «NAVAS DEL MARQUÉS (LAS)»,
  «Código INE: 05168», actualizado a 09-nov-2026. Consulta pública, todos los
  documentos, sin activar «Mostrar históricos» ni limitar a planeamiento general.

## Extracción y significado

El inventario muestra **32 entradas** distribuidas en **1–15, 16–30, 31–32**.
Se recorren los enlaces JavaScript reales de paginación; se ignoran los enlaces
para ordenar columnas. Se comprueban el total, los intervalos completos y la
unicidad de identificadores antes de escribir. Cambios de formato, totales
inconsistentes o páginas ausentes provocan error, sin producir una salida parcial.

Se extraen **30 instrumentos/proyectos** de los libros PU/GU. Se excluyen el
convenio urbanístico UA-5 (CU, 285063) y la sentencia de anulación del sector
Ciudad del Golf (292269). El plan parcial de ese sector permanece como entrada
del archivo: esto no afirma su validez jurídica actual. No se reconstruye el efecto
de sentencias ni la vigencia jurídica consolidada del planeamiento.

Cada ID `cDocId` identifica una entrada de instrumento. Sus memorias, planos y
otros ficheros se agrupan en `documentos`, con nombre original y enlace
`openFichero.do?cFicheroId=…`. Se mantienen por separado las modificaciones y
rectificaciones que el archivo identifica como entradas distintas. Hay **74 enlaces
a ficheros**, agrupados en **26 instrumentos**. Las otras **4 entradas** carecen
de ficheros en el listado; conservan su ID y el enlace oficial al boletín derivado
del `doGoBoletin` publicado en la fila. Los enlaces a boletines se retienen, sin
interpretar sus textos. Si se introduce paginación en los listados de ficheros,
el adaptador falla explícitamente para evitar truncarlos.

Ejemplos observados:

- NUM, ID 281075: acuerdo 2003-04-30, publicación 2003-07-07, seis ficheros.
- Modificación 30, ID 300750: acuerdo 2025-05-15, publicación 2025-05-29.
- Modificación 27, ID 301426: acuerdo 2023-12-20, publicación 2026-02-03.
- Planes Peña Elizandera y Los Maizales: publicación ausente; se conserva `null`.

`fecha_publicacion` y `fecha_acuerdo` reproducen columnas distintas. No se
sustituye una por otra, ni se infiere `fecha_aprob`, fase o concesión. Los títulos
conservan incluso las erratas del archivo. No se extraen coordenadas de mapas,
centroides ni direcciones; geometría, latitud y longitud quedan nulas y
`publication_ready=false`.

## Validación y evidencia local

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_las_navas_del_marques -v
```

Seis pruebas correctas: fechas y ausencias, paginación frente a ordenación,
agrupación de adjuntos, exclusiones semánticas, errores de cobertura/identidad,
manifiesto y licencias desactivadas. La extracción real se ejecutó mediante
`load_manifest` y `load_portal_adapter`, llamando a `backfill_proyectos` con
`capture_dir=evidence/live-captures`.

- `evidence/proyectos.jsonl`: 30 registros reales, IDs únicos, INE verificado.
- `evidence/validation.json`: recuentos, URLs efectivamente consultadas,
  limitaciones, fecha de ejecución y resultado del anotador compartido.
- `evidence/live-captures/source-NNN.html`: respuestas originales, en el mismo
  orden que `source_urls` de validation.json: tres páginas y 26 listados de ficheros.

El anotador compartido clasifica estas entradas como `unknown` y comunica
`adapter_incident/unknown_entity_spike`: no dispone de una regla específica para
la identidad de instrumentos JCyL. Se conserva ese diagnóstico sin alterar la
política compartida ni inventar números de expediente para eludirla. La evidencia
es un inventario de planeamiento revisable, no una autorización de publicación.

Cobertura municipal **parcial**: no es un registro exhaustivo de obras físicas,
contratación o licencias, ni todo el histórico urbanístico. La actualización vuelve
a extraer la instantánea completa, sin watermark que oculte publicaciones tardías.
La evidencia es local y no debe incorporarse al commit.
