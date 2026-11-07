# Oiartzun — INE 20063, Gipuzkoa, País Vasco

Verificado mediante HTTP real el 2026-11-07. Adaptador único:
`municipio.adapters.oiartzun:OiartzunAyuntamientoAdapter`.

## Fuentes oficiales y alcance

La navegación de Hirigintza del Ayuntamiento descubre estos inventarios:

- [Plan General](https://www.oiartzun.eus/eu/Hirigintza/Plangintza_Urbanistikoa:_Plan_Orokorra).
  Nueve fichas: aprobación y ocho capítulos, agrupadas como **un instrumento**.
  La extracción conserva 60 enlaces documentales, incluidas las versiones
  lingüísticas y los planos. Los documentos no se cuentan como proyectos.
- [Modificaciones del Plan General](https://www.oiartzun.eus/eu/Hirigintza/Plangintza_Urbanistikoa:_Plan_Orokorraren_aldaketak).
  Una ficha actual: tercera modificación puntual del HAPO, ordenación de usos
  turísticos y alojamientos. **Un instrumento**, seis documentos (PDF y XLSX).
  No se inventan modificaciones primera o segunda ausentes del inventario.
- [Planeamiento de desarrollo](https://www.oiartzun.eus/eu/hirigintza/plangintza_urbanistikoa%3A_garapen_plangintza).
  Descubierto y capturado: primera página con doce filas y navegación hasta la
  página siete. **Fuera del alcance** del adaptador. No se presenta su primera
  página como extracción completa ni se incorporan esos expedientes.

Se eligió la versión en euskera. La española no tiene necesariamente igual
cobertura ni las mismas fechas de listado (tercera modificación: 17 de febrero
frente a 19 de febrero). No se mezclan las dos versiones como proyectos distintos.
La cobertura es parcial: PGOU y modificaciones publicadas en esos dos inventarios;
no representa todo el urbanismo, obras públicas o histórico de Oiartzun.

## Semántica, documentos y fechas

El PGOU conserva `fecha_acuerdo=2015-03-25`, sustentada por el texto de aprobación
por el pleno de esa fecha. Se informa fase `aprobacion`, sin deducir una fase más
precisa del nombre de un PDF. Su fecha de publicación queda nula: el listado por
sí solo no establece esa semántica.

La tercera modificación conserva `fecha_acuerdo=2026-01-28` y fase
`aprobacion_inicial` de su relato municipal. `fecha_publicacion=2026-02-19`
corresponde a la etiqueta explícita «Boletinean argitaratua: GAO 2026-02-19».
El 17 de febrero del listado se conserva como `fecha_listado`, sin interpretarlo
como acuerdo ni publicación. No se confunde la suspensión de licencias descrita
en ese expediente con una licencia concedida.

Cada registro retiene `fichas_fuente` con título, URL, fecha del listado, inventario,
relato, fechas y documentos. Cada documento retiene su `url_procedencia` municipal.
Los capítulos ambientales/planos incluyen documentos alojados en Google Drive,
enlazados explícitamente por el Ayuntamiento: se conservan sus enlaces sin entrar
en cuentas ni usar credenciales. El resto son adjuntos municipales en
`/fitxategiak/erab_2/`. Se excluye el certificado ENS del pie de página.
Los cuerpos de PDF/XLSX/Drive no se analizan ni se verifica individualmente su
accesibilidad; se acredita la procedencia de los enlaces en el HTML oficial.

## Paginación, actualización y fallos

Los dos inventarios incluidos no presentan paginación en la comprobación actual.
El extractor recorre por cola todos los enlaces `?page=N`, deduplica URLs y fichas,
y no escribe salida si falla una página o documento de detalle. Rechaza paginación
no reconocida, cambios de estructura, inventarios vacíos, detalles sin documentos,
modificaciones sin identificador numérico o fechas incompatibles de etapas distintas.
El límite defensivo de cien páginas produce error; nunca una salida truncada.
La actualización vuelve a leer la instantánea completa; no usa un corte por fecha.

## Geometría y licencias

`geometry_status: unavailable`. Sin coordenadas ni geometría fabricadas;
`publication_ready=false`. La página municipal de
[información geográfica](https://www.oiartzun.eus/eu/Hirigintza/Informazio_geografikoa)
enlaza B5M, catastro de Gipuzkoa y el visor GeoEuskadi. Esos enlaces generales no
acreditan geometría vectorial vinculada a los dos instrumentos. No se han explorado
capas de esos visores ni vectorizado planos PDF.

`licencias.enabled=false`: no se ha identificado en este trabajo un inventario
verificado de licencias concedidas. Los métodos de licencias devuelven vacío con
estado deshabilitado. No se extraen formularios, contratación ni noticias.
`schedule.enabled=false` y `geocode.jitter_missing=false`.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_oiartzun -v`: cinco pruebas pasan, cubriendo
paginación completa y agrupación, separación de fechas, procedencia de documentos
externos, exclusión del pie, fallos de estructura y conservación de la salida anterior.
Se realizó extracción HTTP real con el adaptador cargado mediante el registro y el
manifiesto, incluida la anotación compartida de entidades: **dos registros reales**,
66 enlaces documentales. La política compartida clasifica ambos como desconocidos;
no se fuerza una clasificación residencial a partir del nombre del instrumento.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (recuento, URLs, limitaciones y fechas), HTML de todas las
fichas e inventarios incluidos en `evidence/captures/`, más capturas de descubrimiento
y de información geográfica. No hay cambios compartidos, dependencias, publicación
ni acceso a servicios de producción.
