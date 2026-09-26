# Horcajuelo de la Sierra — investigación portal ayuntamiento

## Resumen

Municipio de la Sierra del Rincón (Reserva de la Biosfera), Comunidad de Madrid. Portal principal en WordPress (tema Avada) con documentación de planeamiento en transparencia; sede electrónica espublico gestiona (tablón vacío en CI); trámites de licencia vía e-Administración y formularios PDF en la web.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web oficial | https://horcajuelodelasierra.es |
| Portal transparencia — ordenación | https://horcajuelodelasierra.es/portal-transparencia/ordenacion-del-territorio-y-obras-publicas/ |
| Ordenanzas municipales | https://horcajuelodelasierra.es/ayuntamiento/normativa-municipal/ordenanzas-municipales/ |
| Trámites | https://horcajuelodelasierra.es/ayuntamiento/tramites/ |
| Bandos / decretos | https://horcajuelodelasierra.es/bandos/ , https://horcajuelodelasierra.es/decretos/ |
| Sede espublico | https://horcajuelodelasierra.sedelectronica.es |
| Tablón sede | https://horcajuelodelasierra.sedelectronica.es/board |
| e-Administración (licencias) | https://sedehorcajuelodelasierra.eadministracion.es/PortalCiudadano/Menus/wfrBienvenida.aspx?param=MjgmMDcx |
| Visor SITCM | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=071 |

## Proyectos / planeamiento

- **Transparencia → Ordenación del territorio:** ~24 PDFs (2023) con avance PGOU / NNSS: acuerdo pleno, memoria, catálogo, normas urbanísticas (7 volúmenes), planos de ordenación (clasificación, calificación, alturas, patrimonio, etc.).
- **Listado:** HTML estático WordPress con enlaces directos a `/wp-content/uploads/2023/07/*.pdf`.
- **No hay** visor de expedientes urbanísticos ni API JSON de proyectos; solo documentación normativa descargable.
- **Sede tablón:** estructura Wicket determinista pero sin filas `preview-document` en el momento de la investigación.

## Licencias de obra

- **No hay** registro histórico público de concesiones de licencia.
- **Formulario:** `MODELO-DE-LICENCIA-URBANISTICA.pdf` en trámites (dic 2025).
- **Ordenanza 4:** `ORDENANZA_4_LICENCIAS_Y_D_RESPONSABLE.pdf` (oct 2025).
- **Tramitación:** sede e-Administración (requiere identificación); tablón espublico para exposiciones cuando proceda.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa vigente `sitcm:VPLA_V_AMBITO`: **0 features** para CD_MUNICIPIO=`071`
  - Capa referencia PGOU 2023: `sitcm:VPLA_V_ORDENANZA_REF_23` — **92 polígonos**, 5 tipos de ordenanza (AMPLIACIÓN DE NÚCLEO, CONSERVACIÓN EDIFICACIÓN TRADICIONAL, EQUIPAMIENTOS Y SERVICIOS URBANOS, NUEVA EDIFICACIÓN EN NÚCLEO TRADICIONAL, VIARIO Y ESPACIOS LIBRES)
  - DS_MUNICIPIO en WFS: `HORCAJUELO DE LA SIERRA`
- **Estrategia:** ingestar polígonos agrupados por `DS_NOMB_ORD` como proyectos SIT; enriquecer PDFs de planeamiento si el título contiene tokens de ordenanza (p. ej. «núcleo», «viario»).
- **Limitaciones:** sin ámbitos UE en capa vigente; PDFs de expedientes sin georreferencia; tablón sede vacío; licencias solo informativas (formularios/ordenanza).
