# la Font d'en Carròs — Valencia — INE 46127

Verificado el 2026-11-09 mediante HTTP público, sin autenticación. Adaptador
municipal único: `municipio.adapters.la_font_d_en_carros:LaFontDEnCarrosAyuntamientoAdapter`.
La extracción real produce **5 instrumentos agrupados y 8 referencias PDF**.
Cobertura parcial del inventario de planeamiento, no un historial exhaustivo de
obras ni de licencias. `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`; todos los registros tienen `publication_ready=false`.

## Descubrimiento y procedencia oficial

- [Web municipal](https://www.lafontdencarros.es/): HTTP 200; enlaza directamente
  su portal de transparencia. Captura local `evidence/home.html`.
- [Departamento de urbanismo](https://www.lafontdencarros.es/va/departament-urbanisme/urbanisme/):
  HTTP 200 pero sin inventario útil en el cuerpo recibido. No genera registros.
- [Portal municipal de transparencia](https://transparencia.lafontdencarros.es):
  HTTP 200; enlace al inventario Urbanisme, identificación municipal y dirección
  de contacto en Valencia.
- [Inventario Urbanisme](https://transparencia.lafontdencarros.es/urbanisme/):
  HTTP 200; visor WordPress con 14 documentos. Cada botón
  `button.doc-viewer__btn` contiene JSON `data-wp-context` con título, identificador
  de publicación y URL PDF. No se depende del único enlace visible «Descarregar
  PDF», que solo corresponde al primer documento. La lista completa está en el
  HTML; no hay paginación en esta fuente. El adaptador rechaza indicadores de
  paginación para evitar una extracción incompleta ante cambios del sitio.

Los 14 PDF del inventario se descargaron durante la investigación como
`evidence/doc-<id>.pdf` (HTTP 200), con transcripción local `.txt` mediante
`pdftotext -layout`. Algunos son escaneados sin texto reconocible. La extracción
del adaptador consulta de nuevo el inventario y descarga únicamente los tres
avisos breves necesarios para fechas y referencias documentales; las demás
referencias se conservan sin exigir OCR. Las capturas de esa ejecución se guardan
como `evidence/live-inventory.html` y los PDF con sus nombres originales.

## Entidades y agrupación

| Instrumento | Documentos del inventario | Alcance |
| --- | --- | --- |
| Pla general | Información pública julio 2018, aprobación provisional abril 2019, plano clasificación concert previ | Un instrumento con documentos de distintas fases; no tres proyectos |
| Normes subsidiàries | Normes subsidiaries | Instrumento normativo urbanístico identificado; escaneado, sin fecha extraída |
| Ordenació d'altures de l'edificació | Partes 1 y 2 | Dos hojas de una misma ordenación; no se presupone un expediente o relación jurídica con las Normes subsidiàries |
| Pla parcial Tossal Gros | Ordenances pla parcial Tossal Gros | Documentación normativa del plan parcial, no una obra ejecutada |
| Pla especial del recinte emmurallat «El Rafalí» | Aviso del plan especial | El PDF municipal identifica el nombre y el acuerdo del pleno |

El plano «concert previ» se conserva con el planeamiento general como antecedente,
sin afirmar que pertenece a la versión de propuesta aprobada provisionalmente en
2019. No se inventan números de expediente. Los identificadores son claves locales
estables por instrumento, no números oficiales.

Se excluyen explícitamente los seis planes de clima/energía, riesgo sísmico,
inundaciones, prevención de incendios, residuos y PUAM: son documentos reales,
pero quedan fuera del alcance seleccionado de instrumentos de ordenación del
suelo. Sus títulos y URL completos figuran en `excluded_documents` en la evidencia,
no se omiten como si el inventario solo tuviera ocho documentos. Tampoco se
convierten medidas internas de esos planes en proyectos de obra. Noticias,
anuncios de contratación y formularios de licencia no son fuentes del adaptador.

## Fechas y enlaces documentales

- [Aviso de información pública del Pla general](https://transparencia.lafontdencarros.es/wp-content/uploads/2026/06/06.-_informacio_publica_pla_general_-_juliol_2018.pdf):
  acuerdo de exposición pública **2018-07-12**, publicación DOCV **2018-07-30**.
  Ambas fechas están en el texto y se conservan en el documento correspondiente;
  no se confunden con una aprobación definitiva. Se retienen el enlace DOGV y la
  carpeta documental citada por el aviso.
- [Aviso de aprobación provisional](https://transparencia.lafontdencarros.es/wp-content/uploads/2026/06/07.-_aprovacio_provisional_pla_general_-_abril_2019.pdf):
  acuerdo/aprobación provisional **2019-04-11**. Se retienen los enlaces al
  certificado plenario, informe de alegaciones y carpeta de propuesta del plan.
  El registro agrupado utiliza esta fecha como `fecha_acuerdo` y `fecha_aprob`;
  `fecha_publicacion` permanece null porque no se acredita una publicación de
  este acuerdo. No se traslada la publicación del trámite de 2018 al de 2019.
- [Aviso del plan especial](https://transparencia.lafontdencarros.es/wp-content/uploads/2026/06/08.-Pla-Especial-de-Proteccio-del-Recinte-Emmurallat.pdf):
  aprobación por el pleno en sesión de **2020-11-12**, sin atribuirle carácter
  definitivo. Se conserva el enlace documental de Google Drive citado en el PDF.

Los enlaces de Google Drive se transcriben desde los avisos municipales y retienen
su procedencia, pero el adaptador no descarga ni enumera esas carpetas. No afirma
cobertura completa de sus contenidos. Las rutas `/uploads/2026/06/` son ubicaciones
de subida/migración del sitio; **no son fechas de aprobación o publicación**.
`fecha` genérica queda null. Las fechas que no figuran en los avisos quedan null.
No se infiere vigencia jurídica actual del mero hecho de estar en el inventario.

## Funcionamiento y validación

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se reutilizan requests/BeautifulSoup del entorno y el ejecutable preinstalado
`/usr/bin/pdftotext`; no se han instalado paquetes ni cambiado dependencias.
Sin pdftotext, la extracción falla explícitamente en lugar de emitir fechas falsas.

- `python -m unittest municipio.test_la_font_d_en_carros -v`: **7 pruebas pasan**.
  Comprueban agrupación y estabilidad de identidad, exclusión de formularios y
  anuncios, fechas de publicación/acuerdo distintas, fechas ausentes, contenido
  vacío, paginación, URL ajena y preservación del resultado previo si falla una
  descarga. También comprueban la carga del manifiesto.
- Extracción real mediante `load_manifest('la-font-d-en-carros')`,
  `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  **5 registros**, 8 referencias documentales, 3 avisos descargados de nuevo y
  analizados, sin coordenadas fabricadas. Se estableció `capture_dir='evidence'`
  únicamente en la configuración de esa ejecución para guardar las respuestas.
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/proyectos.entities.json`, HTML y PDF.
  `validation.json` registra recuento, URL efectivamente consultadas, exclusiones,
  resultado de pruebas y limitaciones.

El clasificador compartido deja los cinco registros como `pendiente` por falta de
identidad administrativa suficiente para su política de actividad; son un
inventario documental agrupado, no actividad publicable validada. No se ha
fabricado un expediente para eludir ese resultado. No hay geometría vectorial
verificada, latitud o longitud: esos campos permanecen null y no se usa un
centroide municipal. No se ha encontrado/verificado un registro público de
licencias concedidas en estas fuentes; el método de licencias está deshabilitado.

Las actualizaciones vuelven a extraer el inventario completo. Las peticiones
tienen timeout, límites de tamaño y comprobación de dominio; una descarga o
estructura inválida aborta antes de reemplazar el resultado previo. La cobertura
seleccionada y los documentos excluidos se devuelven con cada ejecución.
