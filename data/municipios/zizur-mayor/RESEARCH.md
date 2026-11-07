# Zizur Mayor / Zizur Nagusia — INE 31907, Navarra

Verificación directa: 2026-11-07. Adaptador exclusivo de este municipio.
Se revisaron antes de implementar `municipio/manifest.py`, el contrato de
`municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos de
Hernani y Chipiona. No se modifican fuentes compartidas ni dependencias.

## Descubrimiento y fuentes oficiales

- [Urbanismo](https://www.zizurmayor.es/servicios-municipales/urbanismo/):
  página de contacto, no registro de licencias. Captura local `evidence/urbanismo.html`.
- [Plan Municipal](https://www.zizurmayor.es/plan-municipal/): inventario público
  de textos, fichas y planos del Plan Municipal y del Plan Parcial del Sector Ardoi,
  además de sus modificaciones. Fuente recorrida íntegramente por el adaptador.
- [Exposición pública de normativas](https://www.zizurmayor.es/ayuntamiento/exposicion-publica-de-normativas/):
  documentación de la aprobación inicial del nuevo PUM. Segundo inventario recorrido
  por el adaptador; sus veinte anexos pertenecen al mismo instrumento.
- [Transparencia](https://www.zizurmayor.es/transparencia/): revisada para descubrir
  fuentes adicionales. Su apartado EMOT no ofrece enlaces en el HTML observado;
  contiene también información económica y dos carteles de subvenciones de
  climatización escolar. Queda fuera de esta extracción de planeamiento.

La búsqueda web de planeamiento municipal permitió localizar ambos inventarios;
no se usa como semilla una noticia ni se extrae el archivo paginado de noticias.
El adaptador vuelve a descargar las dos páginas oficiales en cada ejecución.
No requiere credenciales, navegador, servicios externos ni instalaciones.

## Resultado real y agrupación

7 registros, 45 enlaces documentales:

| Instrumento | Documentos | Fecha explícita recogida |
| --- | ---: | --- |
| Plan Municipal | 12 | Sin fecha de acuerdo/publicación extraída |
| Modificación del Plan Municipal H-15 | 1 | Publicación BON 2011-05-17 |
| Plan Parcial del Sector Ardoi | 5 | Sin fecha de acuerdo/publicación extraída |
| Modificación de Ardoi H-6/H-9/H-11/H-12/H-13/H-15/H-20/H-21 | 1 | Publicación BON 2013-02-11 |
| Modificación de Ardoi M-8 | 5 | Publicación BON 2013-09-12 |
| Modificación de Ardoi enlazada al BON 179/2017 | 1 | Publicación BON 2017-09-15 |
| Nuevo PUM, aprobación inicial | 20 | Acuerdo plenario 2026-08-25 |

Las publicaciones del BON se transcriben de la fila municipal como
`fecha_publicacion`, conservando el texto en `fecha_publicacion_fuente`.
El PUM tiene `fecha_acuerdo`, con su frase de procedencia: no se confunde esa
sesión con una fecha de publicación, ni se interpretan como aprobación las fechas
de leyes citadas. No se inventan días a partir de años de textos refundidos o
rutas de subida. No se usa un campo genérico `fecha`.

Los documentos comparten la ficha de su instrumento. Se respetan incluso las
listas HTML anidadas: los planos de M-8 no se incorporan a la modificación H-6.
Cada documento conserva título, URL y `source_url`; la modificación de 2017
conserva su enlace histórico original al BON. Los IDs derivan del encabezado del
plan o URL principal de la modificación y no dependen del orden de documentos.
Las fichas de suelo y las propuestas territoriales del nuevo PUM no se convierten
en obras independientes ni en licencias concedidas.

## Cobertura y límites

Es una instantánea del inventario publicado, no un histórico completo de todos los
expedientes, ni un registro de obras ejecutadas o licencias. La propia fuente indica
que parte de la documentación gráfica se consulta en oficinas municipales.
La exposición del PUM acredita aprobación inicial, no definitiva; que la página
siga publicada no prueba que el plazo de alegaciones siga abierto.

No hay paginación en los dos inventarios observados. Si aparecen controles de
paginación, el parser falla explícitamente: no devuelve una primera página como
si fuese la totalidad. La extracción también falla ante pérdida de secciones,
anexos, acuerdo explícito o contenido esperado. Se escribe el JSONL solo después
de validar ambas fuentes, evitando reemplazarlo por una extracción fallida.
`update_proyectos` refresca ambas fuentes completas y no pretende mantener archivo
de documentos retirados. Los cambios estructurales requieren revisión.

`geometry_status: unavailable`: solo se han verificado enlaces a planos PDF,
no una capa vectorial vinculada por expediente. No se extraen coordenadas de
contacto, centroides ni localizaciones aproximadas. `publication_ready: false`.
Licencias, calendario y jitter permanecen deshabilitados en el manifest.
La política compartida anota 4 de las 7 entidades como `unknown`; se conserva ese
resultado para revisión independiente y no se altera el clasificador compartido.

## Validación y evidencias locales

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_zizur_mayor -v
```

5 pruebas pasan: agrupación de modificaciones anidadas, fechas y deduplicación;
acuerdo y anexos del PUM; rechazo de paginación/contenido cambiado/host ajeno;
recorrido del adaptador y preservación de salida ante fallo; identidad y opciones
del manifest. Fixtures sintéticos mínimos en el archivo de pruebas, sin red ni
dependencia de las evidencias locales.

La extracción real se ejecutó mediante `load_manifest('zizur-mayor')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['capture_dir'] = 'evidence'` antes de cargar el adaptador.
Esto comprueba también el registro dinámico y aplica la política compartida.

`evidence/validation.json` contiene recuentos, URLs, limitaciones y resultado del
adaptador. `evidence/proyectos.jsonl` contiene las 7 entidades reales. Las capturas
HTML de los dos inventarios proceden de esta ejecución del adaptador.
Se descargaron además dos muestras documentales (memoria histórica y listado
del nuevo PUM): HTTP 200 y firma PDF válida, con tamaño y SHA-256 registrados en
validation.json. No se afirma haber descargado o interpretado todos los anexos;
la disponibilidad futura de enlaces históricos no está garantizada.
Las evidencias son locales y no forman parte de los cuatro archivos fuente.
