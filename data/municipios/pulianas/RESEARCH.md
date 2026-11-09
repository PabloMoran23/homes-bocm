# Pulianas (Granada), INE 18165

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y selección de fuentes

Se inspeccionaron `municipio/adapters/portal.py`, `municipio/manifest.py`, el
registro de adaptadores y los ejemplos Manlleu, Chipiona y Hernani antes de
implementar el adaptador.

- [Urbanismo municipal](https://www.pulianas.es/areas-municipales/urbanismo/):
  describe funciones del área y el concepto de PGOU, pero no identifica un
  instrumento concreto con documentación. No se convierte en un proyecto.
- [Transparencia municipal](https://ayuntamientodepulianas.sedelectronica.es/transparency):
  enlazada desde la web municipal, muestra 338 elementos bajo Urbanismo, Obras
  Públicas y Medio Ambiente. La navegación utiliza callbacks Wicket; los intentos
  de expansión anónima devolvieron respuesta vacía. No se afirma que el fondo sea
  inaccesible por todos los medios ni se presenta como extraído.
- [Inventario ambiental oficial de la Junta](https://www.juntadeandalucia.es/medioambiente/daepu/):
  formulario público con filtros y paginación explícita. La consulta
  [municipio PULIANAS](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/find?find=findResolucionesFiltered&filter5=PULIANAS&size=25&page=1)
  devuelve una página de una, con tres expedientes de instrumentos reales.

La fuente implementada es **autonómica**, no el inventario completo del
Ayuntamiento. El campo `proyectos.source: ayuntamiento` conserva el canal
municipal previsto por el esquema del repositorio; `portal.base_url`, las notas
y los registros (`source: junta_de_andalucia`) identifican la procedencia real.

## Cobertura observada

| Expediente ambiental | Instrumento | Ficha | Documentos |
| --- | --- | --- | --- |
| EAE/2160/2020 | Plan Parcial PPR-05 del planeamiento general | [20200](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/20200) | 4: admisión/inadmisión, IAE, documento de alcance y anuncio BOJA |
| EAE/2181/2020 | Plan Especial para la innovación de la UE-17 | [24242](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/24242) | 3: admisión/inadmisión, IAE y anuncio BOJA |
| EAE/2558/2025 | Plan Parcial PPI-02 | [52040](https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/52040) | 1: admisión/inadmisión |

Cada expediente ambiental produce un registro con todos sus documentos, no un
registro por PDF. Los identificadores se derivan del expediente; se agrupan
fichas adicionales con el mismo expediente y se retienen sus URLs. No se presume
que diferentes expedientes ambientales correspondan al mismo instrumento sin
prueba documental. Los títulos se conservan de la ficha, incluido su prefijo de
resolución. Los ocho PDF se descargaron y sus textos confirman Pulianas y los
instrumentos/expedientes. Se conservaron HTML, PDF y texto extraído bajo
`evidence/`. No se incluyen noticias, anuncios de contratación, modelos de
solicitud ni ordenanzas como proyectos o licencias concedidas.

El filtro corresponde al municipio **principal**; no incluye búsquedas por
«Otros Municipios». No cubre todos los planes municipales, obras públicas,
licencias ni posibles documentos fuera de este inventario ambiental. La presencia
en el inventario no demuestra vigencia, ejecución, aprobación urbanística ni
concesión de licencia. Licencias, programación y jitter quedan desactivados.

## Fechas, documentos y geometría

El listado mantiene fechas de primera resolución, aunque las fichas contienen
actuaciones ambientales posteriores. Se guarda `fecha_resolucion_ficha` y, por
PDF, `tipo_fuente`, `fecha_resolucion_fuente`, `source_url` y URL de descarga.
No se interpreta «Admisión/ Inadmisión Trámite» como resultado favorable.
`fase`, `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulos.

La tabla etiqueta todas las fechas «Fecha de Resolución», incluso en filas BOJA.
La comprobación documental confirma que **no son fechas de publicación**:
PPR-05 tiene anuncio de 22/12/2020 publicado en BOJA 251 de 31/12/2020;
UE-17 tiene anuncio de 21/07/2021 publicado en BOJA 142 de 26/07/2021.
Por ello también `documentos[].fecha_publicacion` queda nula: el parser de HTML
no extrae fechas del contenido PDF. Las discrepancias se documentan sin
sobrescribir los datos literales de la ficha. Las coordenadas, lat/lon y geometría
quedan nulas; `publication_ready: false`, `geometry_status: unavailable`.

## Implementación y validación

Se recorre desde página 1 hasta el total declarado; no hay recorte silencioso.
Cambios de esquema, identidades municipales incorrectas, páginas repetidas,
variación del total durante la extracción, falta de documentos o más de 100
páginas provocan error antes de reemplazar la salida. Si las fichas incorporan
paginación documental reconocible se exige revisar el parser. Una actualización
refresca el inventario completo, incluidos documentos añadidos a casos antiguos.
Se eliminan identificadores de sesión de los enlaces persistidos.

Pruebas offline:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pulianas -v
```

Resultado: cinco pruebas correctas. Cubren identidad y esquema, exclusión de
formularios, fechas sin promoción a aprobación/publicación, enlaces y agrupación
documental, recorrido de dos páginas, aislamiento de expedientes, fallo sin
sobrescribir una salida completa y requisitos del manifest.

Ejecución real mediante `load_manifest('pulianas')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`adapter.config['capture_dir']='evidence'`. Resultado: **3 registros, 8 documentos,
1 página**. La política compartida del registro clasificó los tres registros sin
entidades desconocidas. `evidence/validation.json` incluye recuento real, URLs,
limitaciones, comprobaciones HTTP/PDF y capturas de texto. Evidencia local no
versionada. No se ejecutó publicación, base de datos ni geocodificación.
