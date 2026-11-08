# Villacañas (Toledo), INE 45185

Verificado en vivo el 2026-11-07 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Un adaptador municipal; cobertura deliberadamente parcial: **un instrumento real,
el POM, con nueve documentos**, sin afirmar que sea una versión consolidada con
todas las modificaciones posteriores. No es un inventario de licencias ni obras.

## Fuentes oficiales y descubrimiento

La [portada municipal](https://www.aytovillacanas.com/) responde HTTP 200 y enlaza
el área Urbanismo y su catálogo de trámites. Las rutas SEF de esa área devolvieron
HTTP 403 durante la investigación. La consulta pública equivalente de Joomla sí
responde HTTP 200, sin autenticación:

- [Catálogo Trámites, página 1](https://www.aytovillacanas.com/?option=com_content&view=category&id=109): cinco artículos, contador «Página 1 de 2».
- [Página 2](https://www.aytovillacanas.com/?option=com_content&view=category&id=109&start=5): dos artículos, contador «Página 2 de 2».

Se recorren ambas páginas. Siete fichas de Urbanismo enlazan seis PDF distintos;
«Anexos» y «Catálogo» comparten `gestion.pdf`. Las fichas y sus fechas se conservan
en `documentos[].procedencia`. Se verificaron también las fichas 4949–4952 mediante
`/?option=com_content&view=article&id=...`; no añaden otros documentos y los artículos
relacionados incluyen noticias ajenas al planeamiento, que se excluyen.

Los tres volúmenes textuales se localizaron mediante búsqueda pública del dominio
oficial (`site:aytovillacanas.com`, planeamiento, memoria y normas). Actualmente no
son los destinos de las fichas con esos nombres. Se descargan directamente y se
valida su contenido en cada ejecución, conservando esa diferencia de procedencia.
Todos los enlaces siguientes respondieron HTTP 200 en la extracción real:

| Documento | URL oficial | Procedencia y comprobación |
| --- | --- | --- |
| Memoria del POM | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/memoriavilcan.pdf | PDF textual; cabecera del POM y pie `POM. Villacañas Doc.Refundido-Julio 01.v1` |
| Normas urbanísticas | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/normasvilcan.pdf | PDF textual del mismo documento refundido |
| Anexos normativos | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/anexosvilcan.pdf | La introducción identifica expresamente su pertenencia al POM |
| P-1 Clasificación del suelo | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/clasficaci_n.pdf | Ficha 4949, rotulada «Memoria» |
| P-2 Calificación del suelo | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/calificacion.compressed.pdf | Ficha 4950, rotulada «Normas» |
| P-3 Gestión del suelo | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/gestion.pdf | Fichas 4951 «Anexos» y 4952 «Catálogo» |
| P-5 Red de abastecimiento | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/abastecimiento.pdf | Ficha 4953 «Inventario Abastecimiento» |
| P-6 Red de saneamiento | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/saneamiento.pdf | Ficha 4954 «Inventario Saneamiento» |
| P-7 Catálogo de bienes protegidos, núcleo urbano | https://www.aytovillacanas.com/images/estatico/ayuntamiento/urbanismo/catalogo-bienes.pdf | Ficha 4955 «Inventario Catálogo de bienes» |

Se renderizaron e inspeccionaron visualmente los seis planos con `pdftoppm`:
los cajetines identifican Ayuntamiento de Villacañas (Toledo), Plan de Ordenación
Municipal y sus títulos/números reales. Son planos del mismo instrumento, no seis
obras nuevas. No se ha inventado un P-4 ausente ni convertido los sectores descritos
en los anexos en proyectos independientes.

## Semántica y límites

Las siete fichas indican publicación el **24/03/2025**. Esa fecha se registra
exclusivamente como `fecha_publicacion_ficha` de la procedencia. Julio de 2001 es
la edición documental, no una fecha completa de acuerdo. Algunos PDF contienen
marcas de impresión de 2003; tampoco son acuerdos. El texto incluye antecedentes
y reglas generales de entrada en vigor, que no acreditan la fecha final de
aprobación de este documento. Por ello `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` del instrumento quedan nulos.

El catálogo sigue ofreciendo estos planos antiguos; no se afirma haber obtenido
el planeamiento consolidado vigente, todas sus modificaciones, expedientes de
obras ni un registro de licencias concedidas. No se extraen formularios, anuncios
de contratación o noticias como licencias/proyectos. `licencias.enabled=false` y
sus métodos producen salida vacía con estado `disabled`.

Los planos PDF no se han georreferenciado. `lat`, `lon` y `geometry` permanecen
nulos, `publication_ready=false`, `geocode.jitter_missing=false` y
`schedule.enabled=false`. No se sustituye geometría por el centro municipal.
El clasificador compartido devuelve `unknown` para este instrumento de
planeamiento; no se fuerza una categoría de edificio u obra pública.

## Comportamiento del adaptador

Carga el inventario actual, descubre los desplazamientos de paginación y verifica
que visitó exactamente todas las páginas declaradas. Página repetida, contador
inconsistente, páginas inaccesibles o límite de 50 páginas abortan sin reemplazar
la salida anterior. No hay truncamiento silencioso. Solo se agrupan los seis
planos revisados; un PDF urbanístico nuevo o desconocido obliga a revisar su
pertenencia al instrumento. Exige todos los planos revisados y las tres cabeceras
y versiones textuales del POM antes de emitir el registro.

Cada ejecución descarga los nueve PDF, verifica su cabecera binaria, y extrae el
texto de los tres volúmenes con el ejecutable **pdftotext ya instalado**. No se
instalan dependencias. HTTP tiene timeout de conexión/lectura de 15/60 segundos,
límite de 2 MB para HTML y 15 MB por PDF; la extracción textual tiene timeout de
45 segundos. Actualización y backfill regeneran una instantánea completa con ID
estable del instrumento y deduplicación por URL, reteniendo ambas procedencias
de `gestion.pdf`. Escritura final mediante reemplazo de un temporal.

## Validación y evidencia local

- `.../venv/bin/python -m unittest municipio.test_villacanas -v`: **9 pruebas OK**.
  Cubren agrupación/procedencia, fechas nulas del instrumento, paginación Joomla,
  páginas ausentes/repetidas, rechazo de documentos desconocidos, contenido de
  otro municipio, exclusión de formularios/noticias y carga del manifiesto.
- Extracción real mediante `load_manifest('villacanas')`,
  `load_portal_adapter(manifest)` y `backfill_proyectos(...)`: **1 registro,
  9 documentos, 2 páginas, 11 URL consultadas**, estado `ok`.
- Para conservar capturas, se añadió únicamente en memoria
  `manifest.portal.config['evidence_dir'] = str(Path('evidence').resolve())` antes
  de cargar el adaptador; el manifiesto no fija rutas locales.
- `evidence/proyectos.jsonl` contiene el registro real y la anotación semántica
  del cargador compartido; `evidence/validation.json` contiene conteo, URL,
  limitaciones, runtime y fecha de comprobación. `evidence/` también conserva
  los HTML, nueve PDF, textos y las imágenes de inspección. Es evidencia local,
  ajena a los cuatro archivos fuente entregados.

No se han modificado fuentes compartidas, dependencias ni configuración Git;
no se han ejecutado operaciones de publicación o despliegue.
