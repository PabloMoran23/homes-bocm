# Cúllar Vega — INE 18057, Granada

Investigación y extracción real: 2026-11-08. Adaptador único con cobertura
parcial del inventario documental municipal de planeamiento. No es un registro
de licencias concedidas, ni un inventario completo de obras o expedientes.

## Fuentes oficiales consultadas

- https://www.cullarvega.com/urbanismo/ — HTTP 200. Fuente de extracción:
  sección «NORMAS SUBSIDIARIAS», con descripción explícita de la aprobación
  definitiva, referencias a dos publicaciones BOP y tres planos de zonificación.
  Página completa sin paginación observada. El adaptador rechaza controles de
  siguiente página, en vez de truncar resultados. No recorre noticias ni toma
  menús, formularios o listas de fases como expedientes.
- https://www.cullarvega.com/wp-content/uploads/2024/03/NNSS-aprobadas-Junta.pdf
  — HTTP 403. Se retiene el enlace y la atribución de la página municipal; no
  se afirma haber leído el documento. La carpeta de carga 2024/03 no acredita
  ninguna fecha de aprobación o publicación.
- https://bop2.dipgra.es/opencms/opencms/portal/index.jsp?opcion=listaEventos&fecha=24/04/2009
  y https://bop2.dipgra.es/opencms/opencms/portal/index.jsp?opcion=listaEventos&fecha=08/02/2011
  — redirigen a https://bop.dipgra.es/publica/consulta-de-bops/ (HTTP 200).
  Las fechas y títulos se extraen de la referencia escrita por el ayuntamiento,
  no del buscador genérico. No se han contrastado los boletines originales.
- https://www.cullarvega.com/wp-content/uploads/2024/05/Zonificacion-usos-Ventorrillo.pdf
  , https://www.cullarvega.com/wp-content/uploads/2024/05/Zonificacion-usos-Ambroz.pdf
  y https://www.cullarvega.com/wp-content/uploads/2024/05/Zonificacion-usos-Cullar.pdf
  — enlaces del mismo apartado, conservados como cartografía publicada allí,
  sin verificar su contenido ni su pertenencia formal a una versión del plan.
  No generan tres instrumentos adicionales.
- https://www.cullarvega.com/obras-y-servicios/ — HTTP 200: contactos y formulario
  de aviso de incidencia, sin inventario de proyectos utilizable en esa página.
- https://cullarvega.sedelectronica.es/transparency — HTTP 200: índice de carpetas
  con contadores y «Mostrar más». No se extrae ni se reclama cobertura de este
  repositorio; sus contadores no son proyectos y su paginación no se recorta.

## Registros y semántica

1. Revisión de las Normas Subsidiarias: un instrumento, con enlace al documento,
   referencia BOP y tres planos asociados al apartado. La narrativa municipal
   acredita `fecha_aprob=2001-03-30`; la referencia BOP nº 77 acredita una fecha
   de publicación citada por la fuente `2009-04-24`. No se atribuye a 2009 la
   aprobación de 2001 ni se afirma vigencia jurídica actual.
2. Adaptación Parcial de las Normas Subsidiarias a la LOUA: un instrumento
   separado con referencia BOP nº 26 y `fecha_publicacion=2011-02-08`. No hay
   fecha de acuerdo/aprobación ni fase acreditada en ese apartado: quedan nulas.

`fecha` genérica y `fecha_acuerdo` permanecen nulas. Las fechas se analizan a
partir del texto, no se fijan en el código. Identidades estables por municipio e
instrumento; deduplicación de documentos por URL. Los documentos conservan
etiqueta, URL original, rol y página de procedencia; contenido_verificado=false.
El PGOM sólo se anuncia como iniciado y enumera fases posibles sin documentos:
no se emite como aprobación ni como expediente documental. Los formularios de
obras y declaraciones responsables no se confunden con concesiones. No se usan
anuncios de contratación ni noticias como proyectos.

No hay geometría contrastada, coordenadas ni centroides sustitutos. Todos los
registros llevan `publication_ready=false`, cobertura parcial y limitaciones.
Manifest con INE 18057, Granada, Andalucía, licencias desactivadas, programación
desactivada y geocode.jitter_missing=false. Update renueva la misma instantánea
completa del apartado soportado; no presume historia incremental o eliminaciones
administrativas a partir de ausencias.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_cullar_vega -v`: seis pruebas correctas. Comprueban
  agrupación y exclusiones, semántica de fechas, fechas ausentes, cambios de
  estructura, paginación, dominios imprevistos, identidad y carga del manifest.
- Extracción HTTP real mediante `load_portal_adapter(load_manifest('cullar-vega'))`
  y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: dos registros reales;
  validación de INE, identidad única y ausencia de coordenadas inventadas.
- `evidence/validation.json`: recuento, URLs, limitaciones, fecha de extracción y
  resultado de la política compartida de entidades. La política clasifica ambos
  como unknown; no se fuerza una categoría inmobiliaria sin base documental.
- Captura exacta usada por el adaptador: `evidence/urbanismo-live.html`.
  Investigación: `evidence/discovery.json`, `urbanismo.html`, `obras.html`,
  `transparency.html`, `bop-2009.html`, `bop-2011.html` y `nnss-response.html`
  (esta última es la respuesta HTML 403, no un PDF).

Evidencia local, fuera de los cuatro archivos fuente de entrega. Sin cambios de
código compartido ni dependencias. Sin publicación, despliegue ni escritura en
servicios externos.
