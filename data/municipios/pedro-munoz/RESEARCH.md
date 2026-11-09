# Pedro Muñoz — INE 13061, Ciudad Real

Consulta y extracción real: 9 de noviembre de 2026. Comunidad autónoma: Castilla-La Mancha.

## Descubrimiento y fuentes

Se inspeccionaron el contrato `municipio/adapters/portal.py`, el cargador de manifests, el registro dinámico y los ejemplos de Chipiona y Hernani antes de implementar el adaptador. No se modifican componentes compartidos.

El [portal municipal de transparencia](https://www.pedro-munoz.es/portal-transparencia/portal-de-transparencia/), el [área de Urbanismo](https://www.pedro-munoz.es/areas/urbanismo/) y la [categoría Urbanismo](https://www.pedro-munoz.es/category/urbanismo/) permiten descubrir la [categoría oficial Normativa Urbanismo y medio ambiente](https://www.pedro-munoz.es/category/portal-transparencia/normativa/normativa-urbanismo-med-ambiente/). Esta última es el inventario recorrido por el adaptador. Contiene tres fichas, todas accesibles en una sola página, sin paginación visible. El área más amplia mezcla estas fichas con noticias; no se usa como registro de licencias ni como censo de proyectos.

## Resultado y unidad documental

La ejecución viva mediante el adaptador cargado desde el manifest produjo **3 registros**:

- [Plan de Ordenación Municipal](https://www.pedro-munoz.es/urbanismo/movilidad-y-urbanismo/plan-de-ordenacion-municipal-de-pedro-munoz/): publicación CMS 2015-11-24. Un instrumento, con 168 enlaces PDF únicos y su ficha HTML. Incluye memorias, normas, fichas de ámbitos, planos y catálogo de bienes protegidos. Las fichas de sectores, los planos y las fichas del catálogo no se convierten en proyectos independientes. No se deduce fecha de aprobación del año de subida.
- [Convenio para modificación puntual núm. 6 del POM](https://www.pedro-munoz.es/urbanismo/acuerdo-adoptado-en-pleno-sobre-aprobacion-inicial-del-convenio-urbanistico-para-modificacion-puntual-num-6-del-pom-de-pedro-munoz/): publicación 2020-06-25; acuerdo plenario expresamente fechado 2020-05-14. El texto identifica la eliminación de dos viarios entre las calles Almendros, San Pancracio, Ramón y Cajal y Padre Damián. Es la aprobación inicial de un convenio para posibilitar la modificación, no la aprobación definitiva del instrumento ni una licencia otorgada.
- [Convenio de modificación del POM — UA Apartaderos](https://www.pedro-munoz.es/urbanismo/propuesta-para-la-aprobacion-inicial-del-convenio-urbanistico-de-modificacion-puntual-del-p-o-m-anulacion-unidad-de-ejecucion-u-a-apartaderos/): publicación 2023-03-03; sesión plenaria 2023-02-27. La certificación transcrita recoge la adopción del acuerdo de aprobación inicial del convenio. Se conserva la ficha HTML y el certificado PDF. No se afirma que la modificación del POM esté definitivamente aprobada.

Los títulos, descripciones íntegras y documentos se extraen del HTML vivo; no hay registros precargados. Cada ficha conserva su URL y la del inventario. Los documentos están asociados exclusivamente al cuerpo de su propia ficha, excluyendo widgets, noticias relacionadas y navegación. Se deduplican por URL dentro de cada instrumento. Los identificadores se derivan de la URL estable de la ficha.

## Límites y enlaces defectuosos

Cobertura deliberadamente parcial: inventario documental municipal de normativa urbanística, sin garantía de exhaustividad del planeamiento, estado jurídico actual, ejecución de obras o historial de licencias. No se recorren anuncios de contratación ni se convierten formularios o noticias ajenas en proyectos.

La ficha de 2020 publica literalmente `//images/documentos/tu-pueblo/urbanismo-movilidad/2020/200625_mod_pom_6.pdf`. No es una URL municipal válida. Se conserva `href_original`, con `url: null` y estado explícito de enlace no municipal o malformado; no se inventa una reparación. El anuncio íntegro sí está disponible en el HTML municipal y se conserva como documento y descripción del registro.

Dos atributos href del POM contienen saltos de línea dentro de la URL. Se elimina únicamente el espacio para formar la URL utilizable y se conserva también el atributo original. Las descargas del POM están publicadas en el dominio municipal sin `www`; la muestra comprobada redirige al dominio municipal con `www`.

Se verificaron dos muestras mediante HTTP 200, tipo `application/pdf` y firma `%PDF`: la memoria del POM y el certificado de Apartaderos. Se capturaron sus primeros 4096 bytes; no se descargaron ni verificaron todos los PDF. Los enlaces publicados llevan estado de no verificación individual en los registros.

`fecha_publicacion` corresponde al CMS. `fecha_acuerdo` se extrae únicamente de la frase inicial que identifica la sesión plenaria y lleva texto y URL de procedencia; no se confunde con fechas de informes o propuestas posteriores. Se omiten `fecha_aprob`, coordenadas y fases inferidas. Todos los registros declaran `publication_ready: false` y geometría no disponible. El anotador compartido devuelve tres entidades de tipo desconocido: se conserva su decisión sin forzar elegibilidad de actividad.

Licencias, ejecución programada y jitter de geocodificación quedan desactivados en el manifest.

## Reproducción y comprobaciones

Runtime preinstalado utilizado, sin instalaciones:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pedro_munoz -v
```

Seis pruebas offline superadas: exclusión de formularios/noticias/licitaciones, asociación y deduplicación documental, enlace malformado conservado, semántica de fechas, recorrido de dos páginas con vuelta a la primera y rechazo de HTML incompatible sin sobrescribir el resultado anterior. Se comprueba también la carga del manifest.

Extracción real realizada con `load_manifest('pedro-munoz')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Para repetir con capturas, establecer `manifest.portal.config['capture_dir'] = 'evidence/captures'` antes de cargar el adaptador. `update_proyectos` refresca el inventario completo sin filtros temporales que puedan omitir documentos antiguos. El crawler sigue los enlaces de paginación, deduplica páginas y falla ante carga dinámica incompatible o al alcanzar el límite defensivo de 100 páginas, sin escribir una salida parcial.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML de descubrimiento y extracción, y muestras binarias PDF. La validación incluye conteo vivo, URLs de fuente, comprobaciones documentales y limitaciones. No se ejecutaron publicación, base de datos, despliegue ni geocodificación.
