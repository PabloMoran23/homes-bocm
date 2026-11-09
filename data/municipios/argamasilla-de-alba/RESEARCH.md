# Argamasilla de Alba — INE 13019, Ciudad Real

Investigación y extracción real: 9 de noviembre de 2026. Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y alcance

Inventario municipal consultado en vivo:
https://www.argamasilladealba.es/servicios-municipales/urbanismo/urbanismo

La página del Ayuntamiento publica los apartados «Normativa urbanística»,
«Plan de Ordenación Municipal» y «Área de Actuación A3». No es un tablón de
concesiones de licencias. Se revisaron el contrato `municipio/adapters/portal.py`,
el cargador/esquema `municipio/manifest.py` y los ejemplos Chipiona y Manlleu
antes de implementar el adaptador propio. No requiere cambios en el registro
compartido: el manifest apunta a la clase por su ruta de importación.

Se extraen **7 instrumentos/proyectos reales y 12 enlaces documentales**:

- Modificación Puntual de las Normas Subsidiarias (artículo 5 apartado LL).
- Sector Industrial «La Serna IV»: extracto de normativa del sector.
- Sector Residencial «El Rincón»: normativa/plan parcial publicado en el BOP.
- Sector Residencial «Trasera Divino Maestro»: documentación normativa del sector.
- Plan de Ordenación Municipal: anuncios DOCM, BOP y carpeta documental enlazada.
- Proyecto de reparcelación voluntaria del área de actuación A3: certificado,
  anuncio DOCM, anuncio Lanza y proyecto enlazado en Drive.
- Proyecto de urbanización del área A3: anuncio BOP.

Los tres sectores se representan como instrumentos documentados por extractos
normativos; no se afirma que sean proyectos de obras en ejecución ni expedientes
completos. No se convierte cada anuncio o plano en un proyecto separado. El POM
y sus dos proyectos de desarrollo A3 tienen identidades distintas. Los enlaces
repetidos «Descargar PDF» de las tarjetas se deduplican por URL. La Ordenanza de
Edificación genérica se excluye. Noticias, contactos, mapas de oficinas y
solicitudes de licencia no producen registros.

La cobertura es una instantánea parcial del inventario de planeamiento publicado
en esta página, no de todas las obras públicas municipales, ni de todo el
histórico urbanístico. Los apartados seleccionados se sirven completos en una
página, sin controles de paginación observados. El parser rechaza marcadores de
paginación en esos apartados; si aparecen será necesario implementar recorrido
antes de continuar. Las noticias relacionadas quedan fuera del alcance.
No se enumeran las carpetas Drive: sus enlaces se conservan como documentación
municipal externa y esta limitación figura también en la salida de extracción.

## Fechas, procedencia y geometría

Cada registro conserva `inventory_url`, `documentos` con título, URL y contexto
municipal inmediato, además de la descripción original de los proyectos.
Identificadores estables a partir de la URL del extracto sectorial o del título
del instrumento agrupado; sin generar identificadores por fecha de ejecución.

Las tarjetas normativas muestran 23/04/2021. Es una fecha del catálogo/CMS:
se guarda como `fecha_catalogo`, sin convertirla en aprobación o publicación
oficial. La lectura del PDF de El Rincón confirma precisamente que contiene una
publicación BOP de 14/09/2009 y un acuerdo de 11/08/2009, fechas diferentes de
la tarjeta. El adaptador no analiza PDF ni extrae esas fechas del texto binario.
No afirma vigencia actual de esos instrumentos antiguos.

El relato del POM distingue aprobación definitiva del 23/05/2019, aprobación
inicial del 04/07/2018 y publicación DOCM/BOP del 22/12/2021. El anuncio es de
15/12/2021: esa fecha no se usa como fecha de publicación. Se extraen solo
aprobación definitiva y publicación explícitas, conservando el relato completo.

Para reparcelación A3, el HTML identifica el acuerdo del 18/09/2025, pero no
indica en ese párrafo el resultado del acuerdo. Se guarda `fecha_acuerdo` sin
inventar una fase a partir de la mera existencia del certificado. Los anuncios
de 07/07/2025 y 09/07/2025 se conservan con su contexto documental, sin usarlos
como fecha de aprobación definitiva.

Para urbanización A3, el HTML dice «Acuerdo de 06/10/2025, de la Junta de Gobierno
Local de fecha 23 de septiembre de 2025» y afirma aprobación definitiva.
Se extraen 23/09/2025 como acuerdo/aprobación. `fecha_publicacion` queda vacía
por la ambigüedad del primer rótulo. La inspección del PDF
[ANUNCIO_BOP_A3.pdf](https://www.argamasilladealba.es/fileadmin/media/Documentos_nueva_web/Urbanismo/ANUNCIO_BOP_A3.pdf)
confirma BOP número 192, lunes 6 de octubre de 2025, página 9098, y acuerdo de
23/09/2025. No se fija esta corrección documental como constante en el parser.

Ningún registro toma coordenadas de los mapas de las oficinas municipales.
`lat`, `lon` y `geometry` son nulos, `geometry_status=unavailable`,
`publication_ready=false`. Licencias, programación y jitter desactivados.

## Verificación y evidencia local

Pruebas ejecutadas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_argamasilla_de_alba -v
```

Cinco pruebas correctas: agrupación y aislamiento documental, exclusión de
ordenanzas/formularios/noticias, semántica de fechas y geometría, fallo ante
cambio de estructura/enlaces externos inesperados/paginación, contrato de
actualización y conservación de salida anterior ante error, y manifest.
Fixtures pequeñas incluidas en el archivo de pruebas; ninguna depende de la
carpeta local de evidencia ni necesita red.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos`, con la política de entidades compartida: 7 registros,
ninguna entidad desconocida. El método update refresca el inventario completo;
no pretende ofrecer un histórico incremental que la fuente no publica.

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: salida real del adaptador.
- `evidence/validation.json`: total `live_records`, fuentes, limitaciones,
  ejecución de pruebas y hashes/tamaños de los PDF capturados.
- `evidence/urbanismo.html`: captura de la página durante la extracción.
- Once PDF municipales enlazados: descarga HTTP 200 y firma `%PDF` comprobada,
  incluyendo la ordenanza excluida del conjunto de registros. Diez son documentos
  de los instrumentos extraídos; los otros dos enlaces de la salida son Drive,
  conservados sin descargar. `pdftotext` preinstalado permitió contrastar el
  certificado A3, el BOP de urbanización y el documento de El Rincón.

No se ejecutó publicación, geocodificación, sincronización, despliegue ni acceso
a bases de datos. La evidencia permite revisar cobertura y procedencia sin
presentar el inventario como un registro exhaustivo de licencias u obras.
