# Porreres — INE 07043, Illes Balears

Verificado el 2026-11-09 con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

- [Urbanisme i Activitats](https://porreres.cat/ca/urbanisme-i-activitats)
  enlaza a [Urbanisme](https://porreres.cat/ca/arxius-i-documents/urbanisme),
  que separa Expedients, Formularis d'urbanisme y Documents d'activitats.
- [Expedients](https://porreres.cat/ca/arxius-i-documents/expedients)
  es el inventario de entrada del adaptador. Tiene doce entradas superiores
  verificadas: seis carpetas y seis páginas de documentos. Los contadores de
  carpeta cuentan entradas, no necesariamente archivos ni instrumentos.
- [Arxius i Documents](https://porreres.cat/ca/arxius-i-documents) es un índice
  general de veinte páginas que mezcla programas, formularios, actas y otros
  documentos. Se inspeccionó como descubrimiento; no se utiliza ni se presenta
  su primera página como inventario completo de proyectos.
- El enlace municipal a transparencia es
  <https://porreres.eadministracio.cat/transparency>. No se utiliza como fuente
  de datos ni se ha verificado allí un registro de licencias concedidas.

Se recorre completamente el árbol de Expedients salvo el Catàleg de camins,
que se excluye por ser un catálogo administrativo de caminos, sin inferir
obras físicas. No se extraen noticias, contratación ni formularios. La cobertura
es parcial respecto del conjunto de actuaciones municipales; no es un registro
exhaustivo de obras ni una certificación del planeamiento legalmente vigente.

## Instrumentos y agrupación

La extracción real produjo **8 instrumentos**, **148 enlaces de archivo únicos**
y **50 páginas HTML consultadas**:

| Instrumento | Archivos únicos |
| --- | ---: |
| Adaptació NNSS al PTM, versiones y anexos | 107 |
| Catàleg d'elements i espais protegits | 15 |
| Modificació puntual núm. 4 NNSS, SUDO URB-OR-01 / equipamiento docente | 1 |
| Modificació puntual núm. 5 NNSS, UE-6 | 3 |
| Modificació puntual núm. 6 NNSS, fusteria metàl·lica | 3 |
| Modificació puntual núm. 7 NNSS, xamfrans | 5 |
| Redelimitació UA4 | 9 |
| Supressió UA1, UA2 i UA3 | 5 |

La adaptación al PTM agrupa la carpeta Adaptació NNSS al PTM (aprobación
provisional 2012 y esmena 2017), ambas entradas de anexos de la esmena,
y el text refós 2021. No son proyectos nuevos por cada plano, memoria, versión
o anuncio. El resto hereda su identidad de la entrada superior del inventario.
Los documentos se deduplican por URL dentro de cada instrumento y conservan
todas sus apariciones, títulos, metadatos y páginas de procedencia.

La página de la MP5 identifica expresamente **Expedient 343/2020**; se conserva
como numero_expediente. Los identificadores restantes son claves estables
del adaptador, no números de expediente inventados. El clasificador compartido
de entidades puede dejar instrumentos pendientes por falta de referencia
administrativa explícita; sus anotaciones se conservan en la evidencia.

## Fechas, estado y documentos

El portal muestra fechas junto al formato/tamaño de cada archivo. Se guardan
como `fecha_archivo` dentro de cada aparición y se conserva el texto original.
No se asume que sean fechas de publicación del acto, acuerdo o aprobación.
Por ejemplo, el documento «Certificat acord Ple 28 març 2022» figura con
fecha de archivo 28/04/2022: estas dos fechas no son intercambiables.

`fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan
nulos. Un título de archivo que diga «Aprovació definitiva» no certifica por sí
solo el estado actual de todo el instrumento. No se extraen fechas desde URLs,
fechas de firma, títulos ni índices del buscador.

Se conservan enlaces a PDFs y ZIPs oficiales con planos, memoria, normativa,
certificados y edictos. El adaptador no analiza el contenido binario ni extrae
geometrías. La validación descargó tres PDFs de muestra (MP5, MP6 y adaptación
PTM), comprobando HTTP 200 y cabecera PDF; no se afirma haber descargado o
validado todos los archivos. Las páginas HTML y estos PDFs están en evidence/.

No hay coordenadas verificadas: lat/lon/geometry nulos y publication_ready false.
Licencias, ejecución programada y jitter están desactivados en el manifiesto.

## Recorrido, fallos y validación

Se siguen enlaces de carpetas y todas las páginas del paginador bajo la misma
ruta; la instantánea actual de Expedients no presenta paginación. Se controlan
ciclos, URLs externas, redirecciones, páginas sin adjuntos y cambios de layout.
Una nueva entrada superior desconocida o superar 200 páginas causa error antes
de escribir resultados, sin devolver un resultado truncado. Se reemplaza la
salida de forma atómica tras completar todo el recorrido. Update refresca la
misma instantánea completa y no interpreta eliminaciones como revocaciones.

Pruebas offline:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_porreres -v
```

Las siete pruebas cubren fechas, procedencia, agrupación de versiones,
deduplicación, paginación, ciclos, exclusiones, cambios de inventario, contenido
inválido, límites de dominio y configuración del municipio.

Extracción real realizada cargando el manifiesto mediante el registro común:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

manifest = load_manifest('porreres')
manifest.portal.config['evidence_dir'] = 'evidence/captures'
result = load_portal_adapter(manifest).backfill_proyectos(
    Path('evidence/proyectos.jsonl')
)
```

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json` (live_records, source_urls, limitaciones y comprobaciones
de adjuntos), `evidence/tests.txt`, capturas HTML y PDFs de muestra.
No se modifican fuentes compartidas ni dependencias.
