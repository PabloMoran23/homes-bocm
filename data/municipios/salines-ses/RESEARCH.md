# Salines, Ses — INE 07059 — Illes Balears

Verificación y ejecución real: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.salines_ses:SalinesSesAyuntamientoAdapter`.

## Fuentes oficiales y selección

- [Urbanisme](https://ajsessalines.net/ca/arxius-i-documents/urbanisme): inventario municipal que enlaza una carpeta de normas subsidiarias con **31 documents**, además de doce carpetas de guías, solicitudes y acreditaciones. Estos formularios no demuestran concesiones de licencias y se excluyen.
- [00 NORMES SUBSIDIÀRIES DE PLANEJAMENT](https://ajsessalines.net/ca/arxius-i-documents/urbanisme/00-normes-subsidiaries-de-planejament): carpeta oficial completa, servida actualmente sin paginación. Sus 31 tarjetas contienen título, fecha de publicación/subida y enlace PDF del propio ayuntamiento.
- [Exposició pública](https://ajsessalines.net/ca/arxius-i-documents/exposicio-publica): inspección adicional; muestra una ordenanza sobre el informe de evaluación de edificios. No se convierte una ordenanza general en proyecto físico ni se incluye en la extracción.

## Registros y agrupación documental

La ejecución produce **2 registros reales con 31 documentos**:

1. Normas complementarias y subsidiarias de planeamiento de Ses Salines: **30 documentos**, incluidos los dos textos refundidos catalán/castellano, planos de suelo rústico/urbano, profundidad edificable y riesgos, y catálogos de caminos y bienes rústicos/urbanos publicados en la misma carpeta. Se conservan los nombres originales y todos los enlaces, sin convertir cada plano, parte de catálogo o traducción en un proyecto independiente. La agrupación expresa la organización del inventario municipal; no certifica la identidad jurídica o vigencia de cada anexo.
2. Pla especial de reforma interior d'es Camp Lladó - juliol 2021: **1 documento**. Instrumento separado por su título explícito, aunque se publique dentro de la carpeta de normas subsidiarias.

No hay registros precargados: los títulos y documentos proceden de la respuesta HTML en cada ejecución. La fecha `13/11/2025` de los textos refundidos y `03/10/2025` del plan especial se guardan únicamente como fechas documentales mostradas en el portal. “Juliol 2021” permanece en el título y no se interpreta como acuerdo, aprobación o publicación. Los campos de fecha del instrumento, fase, aprobación, acuerdo y coordenadas quedan nulos. `publication_ready=false`, `geometry_status=unavailable`.

## Cobertura y controles

Cobertura completa de esta carpeta actual, **parcial del municipio**: no es un histórico de expedientes, un inventario completo de obras públicas ni un registro de licencias concedidas. No se analizan contenidos PDF, no se verifica vigencia jurídica y no se extraen geometrías de sus planos. Se desactivan licencias, ejecución programada y jitter de geocodificación en el manifest.

El adaptador verifica la existencia de la carpeta en el inventario padre y compara el número de PDF únicos con su contador actual. Rechaza HTML vacío, cambios de encabezado, tarjetas sin título/fecha, documentos de origen inesperado y documentos nuevos que no pueda clasificar. Si aparece paginación, falla explícitamente antes de escribir: no devuelve silenciosamente una primera página incompleta. Las actualizaciones refrescan la instantánea completa; el fichero de estado no representa un cursor histórico.

Se verificó un PDF de cada instrumento mediante HTTP Range: ambos respondieron **206 application/pdf**, con firma `%PDF-`. Solo se capturaron sus primeros 1024 bytes; no se verificó individualmente la descarga de los 31 documentos ni su contenido completo.

## Validación reproducible

Runtime preinstalado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```bash
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_salines_ses -v
```

Resultado: **4 pruebas correctas**. Comprueban agrupación bilingüe y separación del plan especial, fechas documentales, rechazo de formularios/URLs ajenas/paginación/fechas inválidas, discrepancias del contador sin sobrescribir resultados previos, actualización como instantánea y carga del manifest con licencias desactivadas.

Ejecución real mediante `load_manifest('salines-ses')`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `evidence_dir` configurado localmente. Resultado: **2 registros**, **31 documentos**. Evidencias locales, no destinadas al commit:

- `evidence/proyectos.jsonl`: registros reales y anotaciones de la política compartida del repositorio.
- `evidence/validation.json`: contador `live_records`, URLs de fuentes, limitaciones, resultado y comprobaciones PDF.
- `evidence/urbanisme.html`, `evidence/normes.html`, `evidence/exposicio.html`: capturas de fuentes oficiales.
- `evidence/document-1.pdf.prefix`, `evidence/document-2.pdf.prefix`: prefijos PDF verificados.

No se modificaron fuentes compartidas ni dependencias y no se realizaron operaciones de publicación o base de datos.
