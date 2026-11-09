# Ribadesella — Asturias — INE 33056

Comprobado el 9 de noviembre de 2026. Un único adaptador municipal, con cobertura
parcial de proyectos físicos descritos en el inventario oficial PRTR. No es un
registro de licencias, ni un inventario de todas las obras municipales.

## Descubrimiento y fuentes actuales

- Portada oficial: https://www.ayto-ribadesella.es/ . Enlaza «Proyectos Financiados
  en el Ayuntamiento de Ribadesella (PRTR)» desde la navegación municipal.
- Inventario utilizado (HTTP 200 mediante requests):
  https://www.ayto-ribadesella.es/proyectos-financiados-en-el-ayuntamiento-de-ribadesella
  . Artículo Liferay con ocho secciones identificadas por referencia PRTR, no una
  colección de noticias ni anuncios de contratación. El beneficiario declarado
  es el Ayuntamiento de Ribadesella. Se procesa el artículo completo.
- https://www.ayto-ribadesella.es/-urbanismo describe funciones y requisitos de
  solicitud. No contiene concesiones verificadas: no se extraen licencias.
- https://www.ayto-ribadesella.es/obras-servicios-e-infraestructuras describe
  servicios y competencias, no expedientes concretos.
- https://www.ayto-ribadesella.es/normativa-municipal1 lleva a
  https://www.ayto-ribadesella.es/normativa-urbanistica . Esta remite al registro
  regional y al visor de planeamiento, además de documentación PGO/CAU.
- La portada enlaza actualmente la información pública PGO/CAU:
  https://ribadesella.sede.e-ayuntamiento.es/action/infopublica?method=view&id=133849
  . La sede muestra documentos de aprobación provisional modificados y una
  publicación de 18/11/2025, con exposición finalizada el 16/10/2025 y pleno de
  25/06/2025. Estas fechas describen eventos distintos; ninguna se aplica a los
  proyectos PRTR. Esta colección de planeamiento queda fuera del adaptador.

## Registros obtenidos en vivo

Cinco proyectos, cada uno con su título y descripción íntegros de la sección:

1. Ciudades Saludables — C18.I02.P02.SI01. Juegos en parques de Bones, Cuerres,
   Meluerda y Collera; equipamiento deportivo en ocho escuelas rurales. Dos líneas
   de intervención pertenecientes a un proyecto, no proyectos por cada máquina.
2. Recogida de biorresiduos 2022 — C12.I03.P01.S03. Nuevos contenedores y camión
   para recogida selectiva, además de campaña de difusión. Es infraestructura y
   equipamiento municipal, no una licencia ni adjudicación.
3. Mejora de eficiencia y reducción de pérdidas de agua — C05.I01.P02.S06.
   Mejora de arquetas de abastecimiento en Pando y Berbes.
4. Accesibilidad de servicios sociales comunitarios — C22.I03.P01.S05. Bandas
   podotáctiles, oruga salvaescaleras y kit de apoyo; agrupados en un proyecto.
5. Rehabilitación residencial de El Cobayu — C02.I01.P02.S19.PROV.S05. Programa
   concreto de rehabilitación de 96 viviendas en cinco bloques. Su descripción
   habla de previsiones y financiación, no acredita viviendas ya rehabilitadas.

Se excluyen tres secciones con motivos explícitos: compra de libros y Aula Mentor
son adquisiciones culturales/formación sin intervención física; el PSTD en esta
página es un plan turístico agregado sin obras individualizadas. No se crean
registros a partir de logotipos, imágenes, trámites o noticias ajenas.

## Semántica, documentos y cobertura

IDs estables por referencia PRTR normalizada, independiente del orden de sección.
Las descripciones conservan la redacción municipal, incluso erratas y referencias
temporales incompletas. No se transforman anualidades presupuestarias, años en
títulos, marcas de tiempo de imágenes o «mayo de 2023» en fechas exactas de acuerdo,
aprobación o publicación. No se asigna fase administrativa ni estado de ejecución.

La URL de origen identifica el artículo; el título y la referencia identifican la
sección, pues no tiene enlace individual. Los documentos enlazados dentro de una
sección se agrupan en `documentos`, con URL y procedencia. En la captura real esas
cinco secciones no contienen anexos enlazados: `documentos=[]`. Las imágenes de
parques, accesibilidad o edificios son ilustrativas y no se presentan como
documentos técnicos ni instrumentos distintos. El HTML completo queda capturado.

No hay paginación en el artículo revisado. Se rechazan enlaces de paginación en
lugar de devolver una extracción truncada. Las secciones nuevas desconocidas,
referencias ausentes, duplicados contradictorios o desaparición del artículo
provocan error y requieren revisión. Las futuras actualizaciones releen el
inventario completo; no se promete histórico ni detección de bajas como fin de obra.

No hay geometría verificada por proyecto. El visor regional enlazado desde
normativa es http://visorrpgur.asturias.es:8092/Visor_Urbanismo_RPGUR/Visor/VisorRPGUR.php
pero no se ha establecido correspondencia vectorial con estas referencias PRTR.
`geometry_status=unavailable`, `publication_ready=false`; no se inventan coordenadas.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_ribadesella -v
```

Seis pruebas pasan: agrupación y procedencia documental, ausencia de fechas
inventadas, selección de alcance y normalización de códigos, rechazo de inventario
inválido, paginación y duplicados contradictorios; también licencias deshabilitadas
y carga del manifiesto. Los fixtures son sintéticos y no son evidencia de registros.

La extracción real se ejecutó con
`RibadesellaAyuntamientoAdapter('ribadesella', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **5 registros reales**. Evidencias locales, excluidas de los cuatro
archivos fuente: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/prtr-inventory.html` y capturas de navegación. No se ejecutó publicación,
sincronización, despliegue ni acceso a bases de datos.
