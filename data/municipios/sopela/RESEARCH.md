# Sopela — INE 48085, Bizkaia

Verificación: 2026-11-07. Adaptador único para el inventario documental de la
**revisión del PGOU de Sopela**, no para todas las obras o instrumentos municipales.

## Fuentes e identidad

- Inventario actual en castellano: https://sopelaplanorokorra.eus/es/ (HTTP 200).
  La portada en euskera https://sopelaplanorokorra.eus/ también responde HTTP 200.
  Contiene presentación municipal, fases y «Documentos y formularios».
- Acreditación oficial independiente del dominio: anuncio del Ayuntamiento de
  Sopela, BOB-2024a112-(II-3047), publicado el **11 de junio de 2024**:
  https://www.bizkaia.eus/lehendakaritza/Bao_bob/2024/06/11/II-3047_cas.pdf
  Su punto quinto dispone publicar el Avance en sopelaplanorokorra.eus.
  Identifica expediente 987/2022. El anuncio es de exposición pública del Avance,
  no de aprobación definitiva del PGOU. No se añade como proyecto separado.
- Identidad municipal contrastada con la tabla de Eustat, fila 48085 / Sopela:
  https://www.eustat.eus/elementos/ele0016300/adaptacion-del-planeamiento-a-la-ley-22006-de-suelo-y-urbanismo-por-municipios/tbl0016347_c.html
- Descubrimiento adicional: Urbanismo general
  https://udala.sopela.eus/cat/areas-municipales/urbanismo/ devuelve HTTP 403 en
  acceso directo. No se extraen noticias o formularios de esta página.
- Existe catálogo oficial foral de planeamiento:
  https://opendatabizkaia.eus/es/dataset/planeamiento-urbanistico-sopela
  (datos globales y calificación pormenorizada). No se convierte su resumen
  estadístico en supuestos proyectos ni se incorpora como otra fuente al scraper.

## Extracción y semántica

Una instantánea completa de la página del instrumento produce **1 registro con
10 enlaces únicos**: programa y manual de participación, informe previo,
información de talleres, síntesis de información y diagnóstico, informe de
participación, resultados, carpeta del Avance + Documento Inicial Estratégico,
síntesis de sugerencias y criterios y objetivos. Los duplicados de las secciones
Fases / Documentos se agrupan por URL dentro del mismo instrumento.
El cuestionario y el buzón se excluyen. Los documentos auxiliares no se presentan
como obras independientes. La carpeta Dropbox está enlazada por el propio portal;
se conserva su URL completa, pero no se enumera su contenido ni se afirma haberlo
descargado. Los diez son enlaces publicados, no diez PDFs verificados.

Se comprobaron en directo los PDFs «Informe previo» y «Criterios y objetivos».
El segundo se titula «Documento para adoptar los criterios y objetivos para
elaborar el PGOU», Fase 3; su firma digital no es una fecha de acuerdo municipal.
La página contiene también descripciones de fases futuras hasta la aprobación
definitiva: no prueban que esas fases hayan ocurrido. Por ello fase,
fecha_publicacion, fecha_acuerdo y fecha_aprob se dejan nulas. No se extraen fechas
de rutas /uploads/. La publicación BOB de 2024 y el decreto fechado 3 de junio
son eventos de aquel anuncio; no se asignan como fecha global de la revisión.

El ID estable identifica la revisión, no una versión documental. Las actualizaciones
refrescan el mismo expediente. Se capturan todos los botones documentales PDF,
imagen y ZIP del dominio del plan y la carpeta externa del Avance. Se retienen
futuros documentos compatibles sin límite numérico. No hay paginación activa:
es una página única del instrumento. Si aparece paginación o desaparecen los
documentos estructurales requeridos, el parser falla explícitamente.

## Límites y geometría

Cobertura parcial: revisión del PGOU, sin inventario general histórico, licencias,
obras ejecutadas ni garantía de estado administrativo actual. No se atribuye a
la revisión el carácter vigente de las Normas Subsidiarias anteriores.

geometry_status: unavailable

La fuente examinada ofrece documentación y una carpeta, sin una capa vectorial
vinculada verificable al instrumento. No se han vectorizado planos ni consultado
capas GIS externas. Latitud, longitud y geometría nulas; publication_ready=false.
No hay fechas de concesión ni licencias verificadas; sus métodos escriben cero
registros y devuelven disabled. schedule.enabled=false y
geocode.jitter_missing=false.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_sopela -v`: 3 pruebas pasan, con agrupación,
  exclusión de formularios, fechas y geometría nulas, ID estable, rechazo de
  documentos ausentes/paginación y carga de manifiesto/adaptador.
- Extracción real con `load_manifest('sopela')`, `load_portal_adapter(manifest)` y
  `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 1 registro,
  10 enlaces. El wrapper de política de entidades devuelve status=ok, categoría
  unknown (es un instrumento general; no se fuerza una categoría de edificación).
- Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `pgou-live.html`, portadas de investigación,
  `avance-bob.pdf`, `informe-previo.pdf`, `criterios-objetivos.pdf` y textos PDF.
  Las capturas distinguen fuente de descubrimiento, documento y acceso fallido.

No se ejecutan orquestación, geocodificación, bases de datos ni publicación.
