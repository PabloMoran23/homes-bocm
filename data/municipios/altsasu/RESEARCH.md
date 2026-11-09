# Altsasu / Alsasua — INE 31010, Navarra

Verificación y extracción real: **2026-11-08**. Adaptador único del portal
municipal; sin cambios compartidos ni dependencias nuevas.

## Fuentes oficiales y descubrimiento

- Portada: https://www.altsasu.net/ . Enlaza «Proyectos y acciones municipales».
- Transparencia: https://www.altsasu.net/transparencia/ y
  https://www.altsasu.net/transparencia/informacion-institucional-organizativa-y-de-planificacion/
  también enlazan ese inventario.
- Inventario utilizado:
  https://www.altsasu.net/ayuntamiento/proyectos-y-acciones-municipales/
  y sus páginas `?paged=2`, `?paged=3`, `?paged=4`. Todas HTTP 200.
- Otra fuente examinada:
  https://www.altsasu.net/ayuntamiento/ordenanza-y-normativa-municipal/urbanismo/
  contiene ordenanzas y el texto refundido del proyecto de intervención global
  Intxostia (fase 1), enlazado como PDF. Es una fuente distinta, **fuera del
  alcance de este adaptador**. No se presenta la extracción como inventario
  exhaustivo del urbanismo municipal.
- El acceso «Plan urbanístico» de la portada tiene `href="#"`: no se usa como
  prueba de un instrumento ni como fuente cartográfica.

Se ha revisado el contrato de `municipio/adapters/portal.py`, el cargador de
manifiestos y los ejemplos Hernani y Manlleu. El manifiesto identifica municipio,
provincia e INE; mantiene programación y licencias deshabilitadas y no permite
jitter de geocodificación.

## Cobertura y criterio semántico

El inventario accesible hoy mezcla **17 fichas históricas**, obras, campañas y
programas sociales. Accesibilidad actual no significa obra actual. Se extraen
**5 registros reales**, descubiertos desde sus cuatro páginas:

| Ficha oficial | Evidencia de proyecto |
| --- | --- |
| [Actuaciones en el entorno de Dantzaleku](https://www.altsasu.net/actuaciones-en-el-entorno-de-dantzaleku/) | Acondicionamiento de la balsa Siets; la descripción identifica parte de la parcela 640 del polígono 3 y objetivos de intervención. |
| [Nueva escuela de música](https://www.altsasu.net/nueva-escuela-de-musica/) | Proyecto de reforma del antiguo convento de La Compasión, con arquitecto, presupuesto y descripción de actuaciones. La ficha dice «Pendiente de adjudicación»; no se convierte en adjudicación ni ejecución. |
| [Piscina cubierta en Zelandi](https://www.altsasu.net/piscina-cubierta-en-zelandi/) | Construcción de piscina y complejo deportivo, con descripción técnica y cuatro planos PDF. |
| [Plan de movilidad](https://www.altsasu.net/plan-de-movilidad/) | Ficha específica de elaboración del plan, con objetivos y problemas de movilidad. No acredita aprobación ni vigencia. |
| [Ahorro de energía en el alumbrado público](https://www.altsasu.net/proyecto-de-ahorro-de-energia-en-el-alumbrado-publico/) | Instalación de equipos reductores estabilizadores de cabecera de línea, con presupuesto y explicación técnica. |

Las 12 exclusiones se conservan con URL y motivo en `evidence/validation.json`:
propuesta de declaración de área natural recreativa (no acredita obra concreta
ni plan urbanístico); contratación de asesoramiento en jardinería; campaña de
ahorro energético; ordenanza de alumbrado; apuesta energética (campaña que vuelve
a mencionar el proyecto de alumbrado ya recogido); talleres de coeducación;
campaña de elecciones profesionales; Agenda 21 (estrategia general fuera del
alcance físico/urbanístico); plan de igualdad; programas con perspectiva de
género; pacto de conciliación; actividades de conciliación.

No se confunde la contratación de un asesor con una obra. La escuela se admite
por su proyecto arquitectónico y actuaciones detalladas, no por su mención de
adjudicación. No se extraen formularios, anuncios de contratación ni noticias.
Tampoco se afirma disponer de un registro de licencias concedidas.

## Procedencia, fechas, documentos y geometría

Título y descripción proceden del cuerpo de cada ficha, eliminando los botones
sociales y la navegación. Cada registro conserva la URL de detalle, las páginas
del inventario y los documentos encontrados en su propio cuerpo. La piscina
es **un registro con cuatro planos**, no cuatro proyectos. Se descargaron y
verificaron las cabeceras PDF de esos cuatro enlaces; capturas, tamaños y SHA-256
figuran en la evidencia local.

Las cinco fichas no muestran fechas inequívocas de publicación, acuerdo o
aprobación: `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan
nulas. Las rutas de subida, metadatos de migración y fecha de consulta no se
convierten en fechas administrativas. `fase` queda nula: la narrativa de la
fuente no prueba el estado actual de estas fichas antiguas. Se conserva completa
en `descripcion`.

`geometry_status: unavailable`. No hay geometría de proyecto verificada en las
fichas extraídas. Se conservan las referencias descriptivas y los planos sin
transformarlos en coordenadas ni polígonos. Latitud, longitud y geometría nulas;
`publication_ready: false`. El anotador compartido devuelve cinco categorías
desconocidas; no se fuerza ninguna categoría adicional ni se cambia la política.

## Recorrido y mantenimiento

Se siguen todos los enlaces de paginación descubiertos, sin fijar un máximo de
cuatro páginas. WordPress mezcla rutas `/page/N/` con `?paged=M`: prevalece el
parámetro explícito y se normalizan a una URL por página. Se deduplican páginas,
fichas y documentos. Una página repetida, inventario vacío, estructura cambiada,
dominio ajeno, entrada nueva sin revisión semántica o superación del límite de
seguridad de 100 páginas provoca error **antes de sustituir la salida**. No se
publica un resultado truncado. La clasificación explícita cubre las 17 entradas
revisadas; añadir entradas requiere revisarlas, no basta una palabra «proyecto».
Actualización = refresco completo, sin cursor de fecha inventado.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_altsasu -v`, **7/7 correctas**.
Cubren manifiesto, procedencia y agrupación documental, fechas desconocidas,
normalización de paginación, páginas descubiertas más allá de cuatro, exclusión
de servicios, fallo ante páginas repetidas o entradas desconocidas conservando
la salida anterior, rechazo de formularios y licencias deshabilitadas.

Extracción real mediante `load_manifest('altsasu')`, `load_portal_adapter()` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir` local.
Resultado: **4 páginas, 17 entradas revisadas, 5 registros, 4 PDF verificados**.
`evidence/validation.json` contiene `live_records`, URLs, limitaciones, resultado
del anotador y evidencias documentales. HTML y PDF en `evidence/live-captures/`;
capturas adicionales del descubrimiento en `evidence/`. Evidencia local excluida
del control de versiones. No se ejecutó ningún paso de publicación o despliegue.
