# Las Ventas de Retamosa — Toledo — INE 45183

Verificado el 2026-11-09 con el Python preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Adaptador de inventario documental municipal, con cobertura parcial. No es un
registro de licencias concedidas, ni un inventario completo de obras actuales.

## Fuentes oficiales descubiertas

- https://lasventasderetamosa.es/obras-urbanismo/ — HTTP 200, inventario municipal
  de descarga sin paginación observada. Contiene modelos de solicitud, normativa,
  NNSS y tomos de reparcelación. Fuente efectiva del adaptador. Se recorren todos
  los enlaces de la respuesta; no se limita el número de resultados.
- https://lasventasderetamosa.sedelectronica.es/board — HTTP 200. La respuesta
  pública observada ofrece convocatorias de órganos, empleo, padrón fiscal y
  actividades. No demuestra concesiones urbanísticas. No se utiliza como
  inventario de proyectos ni se afirma haber agotado su histórico.
- https://lasventasderetamosa.sedelectronica.es/transparency — HTTP 200. La raíz
  muestra «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (0)», junto con categorías
  institucionales y de contratación. No se interpreta su anuncio de escuela de
  baile como obra física. No se recorren las categorías ajenas al alcance.
- El menú municipal enlaza también a la sede y al perfil del contratante. Las
  licitaciones por sí solas no se consideran proyectos o licencias concedidas.

Las respuestas HTML de las tres fuentes y el resumen `discovery.json` están en
`evidence/`. Los modelos de solicitud, declaraciones responsables, autoliquidación
ICIO, ordenanzas generales, convocatorias y noticias ajenas quedan excluidos.

## Registros y procedencia documental

La extracción en vivo genera **2 registros**, agrupando **6 enlaces**:

1. **Normas Subsidiarias de Planeamiento de Las Ventas de Retamosa**:
   [texto de las NNSS](https://lasventasderetamosa.es/wp-content/uploads/2024/04/NORMAS-SUBSIDIARIAS.pdf)
   y [plano original](https://lasventasderetamosa.es/wp-content/uploads/2024/04/PLANO-NNSS-ORIGINAL-scaled.jpg).
   La portada escaneada del PDF identifica expresamente el instrumento y el
   término municipal. Se identifica documentación publicada actualmente en la web;
   no se afirma su vigencia jurídica consolidada ni se extraen sus modificaciones.
2. **Proyecto de reparcelación del sector Polígono 5**:
   [proyecto tomo 1](https://lasventasderetamosa.es/wp-content/uploads/2024/04/PROYECTO-REPARCELACION-POLIGONO-5-TOMO-1.pdf),
   [proyecto tomo 2](https://lasventasderetamosa.es/wp-content/uploads/2024/04/PROYECTO-REPARCELACION-POLIGONO-5-TOMO-2.pdf),
   [reparcelación tomo 1](https://lasventasderetamosa.es/wp-content/uploads/2024/04/REPARCELACION-POLIGONO-5-TOMO-1.pdf)
   y [reparcelación tomo 2](https://lasventasderetamosa.es/wp-content/uploads/2024/04/REPARCELACION-POLIGONO-5-TOMO-2.pdf).
   Las portadas/páginas iniciales se descargaron y revisaron visualmente. El
   proyecto tomo 1 identifica municipio, sector y proyecto; el tomo 2 continúa
   las fichas descriptivas. Los otros dos archivos contienen fichas gráficas de
   parcelas resultantes del mismo sector y visados concordantes. No son cuatro
   proyectos distintos ni cuatro concesiones. El mes de redacción y la fecha
   del visado no se convierten en fecha de acuerdo o aprobación municipal.

Cada registro conserva `inventory_url`, `url_documento` y `documentos` con título,
URL e inventario de procedencia. La identidad estable utiliza municipio e
instrumento, no la fecha de descarga ni una referencia de expediente inventada.
Los PDFs y las imágenes de primeras páginas revisadas se conservan localmente.

El archivo municipal [MEMORIAS Y NORMATIVA](https://lasventasderetamosa.es/wp-content/uploads/2024/04/MEMORIAS-Y-NORMATIVA.pdf)
se descargó y revisó: su portada tiene anotaciones de modificación puntual y
sellos. No se fusiona automáticamente con las NNSS originales ni se genera otro
registro sin determinar la identidad de la modificación. Las dos ordenanzas de
edificación también se capturaron para distinguir normativa de instrumentos.
Estas exclusiones hacen que la cobertura sea deliberadamente parcial.

## Semántica y funcionamiento

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` permanecen
null: el inventario no expresa esos datos. La ruta de subida `/2024/04/` no es
una fecha de publicación ni de aprobación. No se hace OCR ni interpretación de
sellos en el adaptador. No se afirma que existan obras en ejecución actuales.

Las imágenes de planos/fichas no son geometría vectorial georreferenciada:
`lat`, `lon`, `geometry` son null y `publication_ready=false`. No se sustituye
por un centroide municipal. `schedule.enabled=false`, `geocode.jitter_missing=false`
y `licencias.enabled=false`.

Una petición HTTP obtiene el inventario; timeout de conexión 10 s y lectura 45 s,
límite de 4 MB con error explícito si se supera. Se exige título municipal,
ambos instrumentos y enlaces documentales HTTPS del dominio oficial. Redirección
inesperada, lista vacía, cambio a login o aparición de paginación producen error;
no se publica una primera página parcial. La selección se limita a los rótulos
verificados de NNSS/plano y los cuatro tomos del polígono 5. Nuevos instrumentos
con otros rótulos requieren ampliar la investigación y el parser. La actualización
refresca la instantánea completa, con reemplazo del fichero tras validar.

## Validación reproducible

- `.../venv/bin/python -m unittest municipio.test_las_ventas_de_retamosa -v`:
  **6 pruebas, OK**. Cubren agrupación, exclusiones, procedencia, ausencia de fechas
  inferidas, ausencia de geometría, identidad estable, rechazo de login/cambios de
  dominio/paginación, actualización y manifest.
- Se cargó el manifest con `load_manifest` y el adaptador con
  `load_portal_adapter`, y se ejecutó `backfill_proyectos` contra la web real.
  Resultado: **2 registros y 6 enlaces**, sin licencias ni coordenadas fabricadas.
- Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
  `urbanismo-live.html`, PDFs y primeras páginas PNG; no se deben incluir en commit.
- El anotador compartido clasifica ambos registros como `pendiente` por carecer
  de identidad administrativa de expediente/acto en sus reglas. Se conserva
  esa anotación, sin forzar elegibilidad como actividad ni inventar expedientes.
  Los instrumentos documentales reales siguen disponibles para revisión.
