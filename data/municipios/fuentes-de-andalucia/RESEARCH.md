# Fuentes de Andalucía — Sevilla — INE 41042

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Fuentes oficiales y descubrimiento

- Web del Ayuntamiento: https://fuentesdeandalucia.org/
- Área de Urbanismo: https://fuentesdeandalucia.org/delegacion-urbanismo-y-obras-publicas/
  La página contiene contacto de la delegación, no un inventario de expedientes.
- Consulta auxiliar de páginas del CMS:
  https://fuentesdeandalucia.org/wp-json/wp/v2/pages?search=urbanismo&per_page=100
  Devolvió cuatro páginas y `X-WP-TotalPages: 1`; no se truncó la consulta.
- Noticia municipal que acredita la procedencia del portal del PBOM:
  https://fuentesdeandalucia.org/el-ayuntamiento-presenta-a-la-ciudadania-el-documento-previo-de-diagnostico-del-nuevo-plan-basico-de-ordenacion-municipal/
  Publicada el **24 de junio de 2026**, informa de una presentación del diagnóstico
  el 23 de junio. Ninguna de esas fechas acredita un acuerdo de aprobación del plan.
- Inventario documental seleccionado: https://nuevoplanfuentesdeandalucia.es/
  Portal específico del nuevo Plan Básico de Ordenación Municipal, enlazado
  expresamente desde el cuerpo de la noticia del Ayuntamiento. Aunque lo opera el
  equipo redactor, su procedencia municipal se comprueba de nuevo en cada ejecución.

## Cobertura y agrupación

Se extrae **un instrumento real**, el nuevo PBOM, con sus documentos agrupados:

1. Manual de participación:
   http://nuevoplanfuentesdeandalucia.es/wp-content/uploads/2024/06/MANUAL-DE-PARTICIPACION.pdf
2. Diagnóstico previo:
   http://nuevoplanfuentesdeandalucia.es/wp-content/uploads/2026/01/PBOM-FUENTES-DE-ANDALUCIA_F2.1-DIAGNOSTICO_FDO.pdf
3. Planos: https://we.tl/t-ZMpkqfcxV2

Los enlaces se conservan tal como se publican. Las variantes HTTPS de los dos PDF
se comprobaron con HTTP 200, `application/pdf` y firma `%PDF-`; se guardaron únicamente
prefijos de 8192 bytes. Tamaños anunciados: 899949 y 49797327 bytes, respectivamente.
No se analizó el contenido completo de los PDF. La disponibilidad y el contenido del
enlace temporal externo a planos no se verificaron.

El manual aparece dos veces en la página: se deduplica por URL. Una imagen de la
plantilla enlaza un PDF de Peñaflor: se excluye por no pertenecer al dominio del
inventario ni ser un enlace documental textual. No se producen registros por cada
fase futura descrita ni por formularios de participación.

El inventario es una página única con anclas internas y paneles de fases; los enlaces
documentales están en el HTML inicial. No hay paginación observada. Si aparecen
controles de paginación reconocibles, el adaptador falla explícitamente para evitar
truncarla. También falla ante pérdida de identidad, diagnóstico o procedencia.

La cobertura es **parcial**: no es el histórico de planeamiento vigente, ni un
inventario completo de obras, ni un registro de licencias concedidas. Las noticias
generales y anuncios de contratación no se convierten en proyectos o licencias.

## Semántica

El portal indica literalmente `FASE ACTUAL: 3`; se conserva ese texto sin atribuirle
aprobación. Los encabezados de aprobación inicial/definitiva forman parte de una
explicación del proceso futuro. `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob`
del instrumento quedan nulas. La fecha de publicación de la noticia se conserva
solo dentro de `fuentes`, con su URL y naturaleza documental.

No se extraen ni inventan coordenadas, geometrías, fechas de aprobación o concesiones.
`publication_ready: false`; la política compartida aplicada por el cargador del
manifiesto clasifica el registro como `pendiente`, con `activity_eligible: false`.
Se conserva ese resultado sin forzar una categoría. La identidad documental del
PBOM está acreditada, pero no su aptitud para publicación/actividad.
Licencias, programación y jitter de geocodificación están desactivados en el manifiesto.

## Verificación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_fuentes_de_andalucia -v
```

Cuatro pruebas correctas: agrupación y fechas, rechazo de contenido vacío/ajeno y
paginación, procedencia dentro del artículo y refresco estable con licencias desactivadas.
Extracción real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos`:
**1 registro**, con anotación de la política compartida. `update_proyectos` realiza
el mismo refresco completo; no utiliza la fecha de la noticia como cursor.

Evidencias locales no destinadas a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML del portal y noticia utilizadas por el
adaptador, páginas auxiliares de descubrimiento y prefijos PDF identificados como
parciales. No se ha utilizado base de datos, publicación, despliegue ni geocodificación.
