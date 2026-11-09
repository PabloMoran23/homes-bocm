# Porcuna (Jaén), INE 23069

Investigación y extracción real: 9 de noviembre de 2026. Adaptador exclusivo de
Porcuna; no requiere dependencias nuevas ni acceso autenticado.

## Descubrimiento y procedencia

La [web oficial municipal](https://www.porcuna.es/) identifica Porcuna, Jaén y
vincula su [portal de transparencia](https://porcuna.sedelectronica.es/transparency)
y [tablón](https://porcuna.sedelectronica.es/board). La sección «7. URBANISMO,
OBRAS PÚBLICAS Y MEDIO AMBIENTE» está en:

https://porcuna.sedelectronica.es/transparency/35b85983-88ff-43eb-985e-f6b74c9f4092/

El adaptador consume dos inventarios municipales específicos actualmente accesibles:

- [7.1 Planeamiento urbanístico](https://porcuna.sedelectronica.es/transparency/11910f2d-ff3b-40e8-9ec4-52a684af7ec9/): cinco documentos.
- [7.4 Obras públicas e infraestructuras](https://porcuna.sedelectronica.es/transparency/160122fa-7bb1-4276-8ea7-50f8cc045082/): tres documentos, dos de ellos del censo de amianto.

Los enlaces de carpetas se resuelven con la acción Wicket obtenida en una sesión
anónima nueva y su cabecera `Ajax-Location`. No se fijan tokens de sesión ni las
URL temporales de los PDF. Los identificadores de registros derivan de la URL
estable de la carpeta, sin incluir acciones de sesión.

## Registros extraídos

| Instrumento o proyecto (nombre de carpeta municipal) | Documentos | Inventario específico |
| --- | ---: | --- |
| MODIFICACIÓN ESTUDIO DETALLE ALINEACIÓN ALHARILLA | 1 | https://porcuna.sedelectronica.es/transparency/ace4cf4f-591b-4346-b8ee-f3c41368b73e/ |
| MODIFICACIÓN ARTÍCULO 174 | 1 | https://porcuna.sedelectronica.es/transparency/6d7643f2-a30c-4733-8797-a39a65d0f4db/ |
| ESTUDIO DETALLE AVENIDA CARDENAL CISNEROS 72 | 3 | https://porcuna.sedelectronica.es/transparency/0d027ec0-76d4-4d43-ab6b-d66a0b7fdc41/ |
| ESTACIÓN DEPURADORA | 1 | https://porcuna.sedelectronica.es/transparency/4ff8a8bf-c988-4192-a11f-36b20a125118/ |

Los documentos se agrupan por carpeta de instrumento, conservando sus títulos,
descripciones literales y enlaces estables `/preview-document/<uuid>` en
`documentos`. La carpeta genérica «ESTUDIO DE DETALLE» es un contenedor; no se
emite como otro proyecto. «PLANEAMIENTO VIGENTE» está vacío y no genera un PGOU
sintético. El censo de instalaciones con amianto contiene dos documentos que se
cuentan al verificar integridad, pero no se convierten en obras.

Los seis documentos conservados se descargaron durante la verificación: HTTP 200
y firma `%PDF-`. Las capturas y sus textos extraídos con `pdftotext` están en
`evidence/`. El anuncio de depuradora es el BOP Jaén 190, de 4 de octubre de 2021,
edicto 2021/4485: inicio del expediente de expropiación forzosa para ejecutar la
«Estación depuradora de aguas residuales y concentración de vertidos de Porcuna»,
con acuerdo provincial del 23 de septiembre de 2021. Documenta una obra física;
no se interpreta como licencia, contratación ni obra terminada.

## Semántica y límites

Cobertura parcial de las dos ramas documentales indicadas, no un histórico
completo del municipio ni una certificación de vigencia. Se excluyen las otras
ramas ambientales, el tablón, noticias y contratación. El tablón consultado
incluye anuncios de información pública de caminos; no se incorporan a esta
extracción. No se ha verificado un registro de licencias concedidas.

El parser extrae metadatos del inventario HTML, no el contenido de los PDF. Deja
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` a null; no utiliza el reloj de
la sede ni la «Fecha de creación» del visor. La revisión de los PDF permite
confirmar la procedencia pero no incorpora fechas estáticas al código. Por
ejemplo, el documento del artículo 174 menciona acuerdo de 25 de septiembre de
2019 y firma de 21 de septiembre de 2020; no son fechas intercambiables. Los
rótulos de aprobación inicial y definitiva de Cardenal Cisneros se conservan en
sus documentos, sin asignar una fase única deducida al registro.

Sin coordenadas ni geometría inferidas; `publication_ready: false` y
`geometry_status: unavailable`. Manifest con licencias, programación y jitter
desactivados.

Cada carpeta recorrida verifica que su número recursivo de documentos coincide
con el contador municipal. Las ramas seleccionadas no muestran paginación en la
captura actual. Si aparece un botón activo «Mostrar más», el adaptador falla de
forma explícita antes de escribir; no recorta silenciosamente a la primera
página. También rechaza cambios de estructura, destinos externos, ciclos,
carpetas pobladas desconocidas y discrepancias de contadores. Los cambios que
necesiten otra agrupación o paginación requieren revisión del parser. Un fallo
no sobrescribe el último snapshot completo. `update_proyectos` refresca el
inventario completo, sin fingir un histórico incremental.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_porcuna -v`: **10 correctas**.
Comprueban agrupación de los tres documentos, semántica temporal, exclusiones,
parser de carpetas, paginación explícita, dominios, contadores, persistencia
ante fallo, actualización y contrato del manifest.

Extracción ejecutada directamente con este runtime:

```python
from pathlib import Path
from municipio.adapters.porcuna import PorcunaAyuntamientoAdapter
adapter = PorcunaAyuntamientoAdapter(config={'evidence_dir': 'evidence'})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado real: **4 registros, 6 documentos**; 8 documentos recorridos contando
los 2 excluidos de amianto. Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, inventarios HTML, visores,
PDF y textos. `validation.json` incluye recuento vivo, URL de fuentes,
limitaciones y comprobaciones documentales. No se ejecutó publicación,
geocodificación ni acceso a bases de datos.
