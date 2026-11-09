# Es Mercadal — INE 07037, Illes Balears

Verificación en vivo: 2026-11-09. Un único adaptador municipal,
`MercadalEsAyuntamientoAdapter`, para inventarios documentales de planeamiento.
Antes de implementarlo se revisaron `municipio/manifest.py`,
`municipio/adapters/portal.py`, el registro de carga y los ejemplos de Manlleu y
Chipiona. No requiere cambios compartidos ni dependencias adicionales.

## Descubrimiento y fuentes oficiales

La [portada municipal](https://www.aj-esmercadal.org/) enlaza el área de
[Urbanisme](https://www.aj-esmercadal.org/Publicacions/Area.aspx?ID=2).
Su apartado «A un clic» enlaza ambos inventarios:

- [Normes subsidiàries vigents](https://www.aj-esmercadal.org/ca/NORMES_SUBSIDIaRIES_ES_MERCADAL/20358).
  La URL enlazada originalmente, `/Contingut.aspx?IdPub=20358`, redirige a esta
  dirección canónica. Contiene revisión NS 1994, modificaciones puntuales,
  estudios de detalle, cartografía y patrimonio.
- [Avanç pla PGOU Mercadal](https://www.aj-esmercadal.org/ca/AVAN_PLA_PGOU_MERCADAL/12605).
  `/Contingut.aspx?IdPub=12605` redirige a esta dirección canónica. Contiene seis
  PDF del avance (memorias, informe ambiental, planos y anexos), etiquetados
  «Març 2012». Se trata de un avance, sin atribuirle aprobación definitiva.

Se descartó la [solicitud de licencia de obras con proyecto](https://www.carpetaciutadana.org/esmercadal/GesServeis/gestion.aspx?IDGESTION=159&IDIOMA=2):
es un trámite de solicitud, no un registro de licencias otorgadas. El listado
noticioso del área y los anuncios de contratación tampoco alimentan el scraper.
No se ha acreditado un registro público exhaustivo de licencias concedidas.

## Unidad de extracción y cobertura

La ejecución real produjo **19 registros y 38 enlaces**: revisión NS 1994,
15 modificaciones (1, 2, 6–12, 16–19, 21 y 23), dos estudios de detalle
(passeig Marítim y carrer Rosari de Fornells) y un avance PGOU. Las ausencias
en la numeración reflejan el inventario; no se crean instrumentos ausentes.

La modificación 9 agrupa memoria y documento de aprobación. Los seis PDF del
PGOU constituyen un único instrumento. El cuadro resumen, revisión,
cartografía (incluidas las siete páginas de series y el enlace antiguo a
planos) y documentos patrimoniales se conservan como documentación de las NS,
sin convertir planos o listados patrimoniales en proyectos independientes.
Cada enlace conserva título literal normalizado, URL y página de procedencia.
Los identificadores derivan del instrumento y no de la posición en la página.

Ambas páginas son inventarios estáticos sin paginación observada. Se procesan
todos los enlaces de su bloque `.PLA_texte`, sin límite de registros. Una
paginación detectada, origen ajeno, enlace no clasificado, inventario vacío o
cambio del título/estructura causa un error, evitando resultados silenciosamente
parciales. Cada actualización vuelve a obtener ambas páginas completas antes de
escribir la salida; no usa un cursor temporal.

La cobertura municipal es **parcial**: no incluye un histórico exhaustivo de
obras, anuncios, licencias ni otros instrumentos no enlazados por estas dos
páginas. Las páginas de series cartográficas se enlazan sin recorrerlas
recursivamente. El adaptador inventaría documentos, no interpreta los PDF ni
certifica su vigencia jurídica. El encabezado municipal «vigents» se conserva
como procedencia, no como verificación jurídica independiente.

No se extraen fechas de aprobación, acuerdo o publicación: todas quedan nulas.
El mes/año del documento no se usa como fecha administrativa; «Aprov.
definitiva» en una etiqueta tampoco aporta fecha de acuerdo. No hay geometría
vinculada verificada: latitud, longitud y geometría nulas,
`publication_ready=false`, sin geocodificación aleatoria.

## Validación y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_mercadal_es -v` (7/7).
Cubren agrupación, procedencia, ausencia de fechas/geometría inferidas,
rechazo de formularios/enlaces desconocidos/paginación, identificadores,
actualización completa, licencias desactivadas y manifest.

Extracción real invocando `MercadalEsAyuntamientoAdapter.backfill_proyectos`
con `capture_dir=evidence` y salida `evidence/proyectos.jsonl`.
`evidence/validation.json` contiene recuento, fuentes, limitaciones, fecha de
consulta y comprobaciones de documentos de muestra. Se descargaron con HTTP
200 y firma PDF la revisión NS y el resumen ejecutivo PGOU; se guardaron sus
PDF y conversiones de texto para inspección. El resumen PGOU identifica el
avance y marzo de 2012; la revisión NS es escaneada y su conversión no ofrece
texto útil (no se hizo OCR ni se derivaron fechas de ella). Esto es una muestra, no una
comprobación de disponibilidad de los 38 enlaces.

Las capturas de portada, área e inventarios, los documentos de muestra y las
salidas JSON permanecen exclusivamente en `evidence/`; no forman parte de los
cuatro archivos fuente entregables. Programación y licencias desactivadas;
`geocode.jitter_missing=false`.
