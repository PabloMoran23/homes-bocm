# Esquivias — INE 45064, Toledo

Verificado el 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.esquivias:EsquiviasAyuntamientoAdapter`.

## Inventarios oficiales y selección

- https://www.esquivias.es/servicios/urbanismo/descripcion-concejalia:
  descripción del servicio, no expedientes. La navegación identifica como sede
  municipal https://aytoesquivias.sedelectronica.es/transparency.
- https://www.esquivias.es/documentos/normas-urbanisticas: ficha antigua con un
  intervalo de fechas del CMS que no se interpreta como aprobación. El enlace
  https://www.esquivias.es/sites/default/files/documentos/normas.pdf devuelve
  HTTP 404. No se genera un instrumento a partir de esa ficha incompleta.
- Sede municipal, portal de transparencia: índice público con categoría
  «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (8)». Sus acciones Wicket son
  dependientes de sesión; el intento anónimo de expansión devolvió cuerpo vacío.
  No se afirma que esos ocho documentos sean ocho proyectos ni se ingieren.
- https://urbanismo.castillalamancha.es/registros/pau-to: registro público oficial
  autonómico de programas de actuación urbanizadora de Toledo. El selector de
  municipio identifica Esquivias con valor interno `1118` (no es su código INE).
- https://urbanismo.castillalamancha.es/registros/pau-to?municipio=1118:
  inventario filtrado, HTTP 200, una fila y sin paginador en esta ejecución.
  Se comprueba también el municipio de cada fila y la provincia en la ficha.
- https://urbanismo.castillalamancha.es/registros/pau/pau-plan-especial-de-reforma-interior-de-mejora-y-anteproyecto-de-urbanizacion-del:
  ficha oficial, HTTP 200. Identifica el PAU, plan especial de reforma interior de
  mejora y anteproyecto de urbanización del P.16, agente urbanizador, uso
  residencial, superficie y asiento registral. Es un instrumento real del registro,
  no un formulario, anuncio de contratación ni una noticia.

La búsqueda también localizó acuerdos autonómicos de la modificación puntual nº 5
(2026) y del proyecto de urbanización P16. El adaptador se limita expresamente al
registro de PAU: no incorpora resultados del buscador ni esos acuerdos como
registros adicionales. No ofrece cobertura completa del planeamiento de Esquivias.

## Semántica y documentos

Resultado vivo: **un instrumento**, agrupando los componentes PAU/PERI/anteproyecto
bajo la identidad estable de su ficha; no tres actuaciones independientes.
`documentos` conserva la ficha HTML como fuente documental y cualquier PDF adjunto
que aparezca dentro del artículo del instrumento. La ficha observada no expone
PDFs técnicos: no se inventan enlaces ni se atribuyen documentos de navegación.

El listado llama a su columna «Fecha de constitución» y usa internamente
`field_fecha_aprobacion`. Para evitar esa ambigüedad, las fechas se obtienen de los
campos explícitos de la ficha: «Fecha de aprobación» = **2021-07-29**;
«Publicación en el DOCM» = **2021-10-04**. La inscripción se conserva como texto:
«Inscrito con fecha 01-12-21. Libro 3 - Folio 1 - Asiento 1». No se convierte en
fecha de acuerdo ni se extraen fechas del reloj del portal o del rastreo.

La aprobación y la publicación se atribuyen a la ficha registral; no se ha
contrastado el PDF del DOCM. La presencia registral no prueba ejecución actual,
concesión de licencia ni vigencia jurídica actual. No se infiere fase de ejecución.
`source: jccm` y `origen: registro_autonomico_pau_toledo` documentan la procedencia
real; `proyectos.source: ayuntamiento` es el selector del pipeline de adaptadores,
según el esquema compartido, no una atribución de autoría municipal a la web JCCM.

No hay geometría verificada: `lat`, `lon`, `geometry` son null y
`publication_ready` es false. Licencias, programación y jitter están desactivados.
La anotación compartida de entidad deja el registro como `pendiente` por evidencia
insuficiente de identidad en su taxonomía; no se cambia esa política ni se afirma
que el registro esté listo para publicación.

## Extracción, paginación y verificación

El valor del filtro municipal se descubre en cada ejecución. Se recorre el
inventario filtrado y todos los enlaces de su paginador; se exige conservar filtro,
host y ruta oficiales. Se deduplican fichas por URL. Una ausencia del inventario,
municipio incorrecto, ficha incompatible, cambio de columnas, redirección inesperada,
respuesta superior a 4 MB o más de 100 páginas produce error antes de sustituir
la salida. Update vuelve a obtener la instantánea completa; no usa una fecha de
inscripción como marca incremental ni conserva registros retirados silenciosamente.

Runtime utilizado en ambas comprobaciones:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_esquivias -v`: **6 pruebas correctas**.
  Comprueban identidad y configuración, fechas distintas y ausentes, agrupación y
  deduplicación documental, rechazo de otras localidades y navegación, filtro
  dinámico, recorrido de dos páginas y conservación de salida ante fallo.
- Ejecución real mediante `load_manifest('esquivias')`,
  `load_portal_adapter(manifest)` y `backfill_proyectos`: **1 registro**, una
  página filtrada y tres peticiones HTTP al registro. Incluye la anotación de
  entidad normal del cargador compartido.
- Evidencia local en `evidence/proyectos.jsonl`, `evidence/validation.json` y
  capturas HTML nombradas por hash de URL. La validación registra hora UTC,
  `live_records`, URLs, resultados y limitaciones. No forma parte de los cuatro
  archivos fuente entregados.

No se han usado bases de datos, credenciales, publicación, instalaciones,
dependencias nuevas ni cambios a código compartido.
