# Rafelbunyol — INE 46207, Valencia

Revisión: 2026-11-07. Adaptador de un inventario municipal real, sin licencias.

## Fuentes y descubrimiento

- Portal oficial de Govern Obert: https://gobiernoabierto.rafelbunyol.es/
- Inventario de planeamiento: https://gobiernoabierto.rafelbunyol.es/t/planeamiento
  (HTTP 200, HTML servido por el portal; no requiere autenticación).
- Inventario adicional identificado, fuera del alcance de este adaptador:
  https://gobiernoabierto.rafelbunyol.es/t/planes-programas
  Contiene agenda urbana junto a planes de materias ajenas al planeamiento.

El inventario se descubrió mediante búsqueda web restringida al municipio, y se
consultó directamente. El portal identifica Ayuntamiento, dirección Pl. Puríssima 1,
46138 Rafelbunyol y enlaces a la sede y web municipales. La raíz de
https://www.rafelbunyol.es cerró la conexión durante la comprobación directa;
esto no afecta al inventario accesible del subdominio oficial.

El inventario contiene «Text consolidat de planejament» y «Planejament urbanístic
vigent». Este último incluye normas, modificaciones y planimetría. Se implementa
**únicamente la tabla completa «Modificacions puntuals»**, no una noticia fija ni
un anuncio de contratación. Sus 13 entradas documentales corresponden a **11
instrumentos**, con los casos de agrupación verificados abajo. La cobertura es
parcial respecto al conjunto de proyectos, obras y planeamiento del municipio.
No se afirma recoger todo el histórico ni expedientes en tramitación fuera de esta
tabla. No se convierten mapas, formularios, noticias ni licitaciones en proyectos.
El texto consolidado es una compilación informativa y no se añade como otro
instrumento ni se generan registros por cada plano.

## Identidad y agrupación de documentos

El identificador estable es municipio + número de modificación, independiente de
la fecha y del prefijo variable de subida del PDF. `expediente_grupo` conserva la referencia del instrumento (modificación puntual y
número), no un número de expediente administrativo inventado. Se conservan todos los enlaces,
títulos originales, fechas de catálogo y SHA-256 de los PDFs descargados.

- Catálogo «8» enlaza `1752739123modificacion_puntual_8_0.pdf`, un BOP de
  3 de febrero de 2007. «8.2» enlaza
  `1752739124modificacion_puntual_8.2.pdf`, DOGV 5481, 30 de marzo de 2007.
  Este segundo PDF identifica expresamente la misma modificación **8**, expediente
  PL-57/2006, resolución de 14 de diciembre de 2006, y remite al BOP anterior.
  Ambos documentos se agrupan en el instrumento 8.
- Catálogo «11» enlaza `1752739124modificacion_puntual_11.pdf`, publicación
  DOGV 6394, 10 de noviembre de 2010, que menciona acuerdo del 1 de octubre de
  2010. Catálogo «12» enlaza `1752739123Mod_11_NNSS.pdf`: su portada escaneada
  identifica «MODIFICACIÓN Nº 11», julio 2010, y diligencia de aprobación del
  1 de octubre de 2010. Se agrupa con 11, **no se inventa una modificación 12**.
  Portada renderizada conservada en `evidence/mod-13-cover.png`.
- El título de catálogo 7 concatena una referencia a 8. Se mantiene íntegro como
  título documental; no genera un instrumento adicional.

Las excepciones 8.2/12 están condicionadas al nombre de documento revisado; un
cambio de enlace provoca error para revisión. La selección normal no fija el
número de registros y permite nuevas modificaciones con nuevos números.

## Fechas y estado

La página sólo dice «Fecha». Hay discrepancias: para 8 y 8.2 el catálogo indica
03-07-2007 y 30-08-2007, mientras los boletines son de febrero y marzo de 2007.
Por ello **ninguna fecha de catálogo se interpreta como publicación o acuerdo**.
Se conserva en cada documento como `fecha_catalogo`, junto a la etiqueta literal.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. Las
fechas mencionadas aquí sirven como evidencia de revisión, no como valores
extraídos dinámicamente del HTML. Los PDFs no se parsean para fechas en ejecución.
La procedencia «planeamiento vigente» describe la clasificación municipal; no se
asigna una fase de aprobación a partir del nombre de tabla.

## Extracción y límites operativos

Cada ejecución descarga el inventario y todos los PDFs descubiertos, valida HTTP,
host final, firma PDF y límites explícitos de tamaño; un fallo impide reemplazar la
salida previa. El refresco incremental repite la instantánea completa sin utilizar
fechas como marca de avance. No existe paginación en la tabla revisada. Si aparece
un enlace siguiente o paginación por parámetro, el adaptador falla explícitamente;
no acepta una primera página truncada. También rechaza estructura inesperada,
fechas inválidas, enlaces ajenos y un inventario vacío.

Las capturas opcionales usan `config.evidence_dir`; el manifest no fija rutas
locales. No se necesita sesión autenticada. Las licencias están deshabilitadas:
no se ha verificado un inventario público de concesiones. Los métodos de licencias
escriben un JSONL vacío y devuelven estado disabled.

## Geometría

`geometry_status: unavailable`. El portal ofrece planimetría PDF, pero no se ha
verificado una capa vectorial por identificador de instrumento. No se digitalizan
PDFs ni se atribuye el centro municipal a cada modificación. Geometría, latitud y
longitud nulas; `publication_ready: false`. No hay jitter.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_rafelbunyol -v` — 5 pruebas:
agrupación 8/8.2 y 11/12, procedencia y semántica de fechas, deduplicación,
rechazo de paginación/cambios de fuente, carga del manifest/licencias deshabilitadas
y conservación de la salida ante fallo de red.

Extracción real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['evidence_dir']='evidence'`. El wrapper normal de política
de entidades también se ejecuta. Resultado: **11 registros reales, 13 PDFs**.
`evidence/validation.json` registra recuento, URLs, limitaciones y resultado de
política. `evidence/planeamiento.html`, PDFs con hash y capturas de revisión
permiten comprobar el resultado. Evidencias locales excluidas de los cuatro
archivos fuente. Sin publicación, despliegue, DB, dependencias nuevas ni cambios
compartidos. `schedule.enabled=false`, `licencias.enabled=false`,
`geocode.jitter_missing=false`.
