# San Lorenzo de El Escorial — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.aytosanlorenzo.es |
| Sede electrónica (eAdmin add4u) | https://sede.aytosanlorenzo.es/eAdmin |
| Tablón digital | https://sede.aytosanlorenzo.es/eAdmin/Tablon.do?action=verAnuncios |
| Catálogo trámites | https://sede.aytosanlorenzo.es/eAdmin/Registrar.do?action=listadoEntradas |
| Portal trámites informativos | https://tramites.aytosanlorenzo.es |
| Transparencia — planeamiento | https://transparencia.aytosanlorenzo.es/urbanismo-y-obras-publicas/planeamiento/ |
| Visor SIT Comunidad de Madrid | https://idem.madrid.org/cartografia/sitcm/html/visor.htm |

## Cómo se listan expedientes / proyectos

1. **Tablón eAdmin (HTML):** secciones por categoría (Urbanismo, Notificaciones, etc.). Cada fila tiene título, periodo de exposición y enlace `Tablon.do?action=verAnuncio&id=…` con PDF vía `abrirOriginal('token')` → `ValidarDocumento.do`.
2. **Transparencia (WordPress Avada):** página única de planeamiento con secciones `<h4>` (Normas Subsidiarias, modificaciones puntuales, planes parciales/especiales) y listas `<li>` con enlaces directos a PDFs en `aytosanlorenzo.es/wp-content/uploads/` o BOCM.
3. **No hay** listado público de expedientes urbanísticos individuales ni API JSON; el acceso a expedientes requiere certificado (trámite 136).

## Cómo se publican licencias

- **Sin dataset de concesiones:** no hay tablón ni CSV de licencias otorgadas.
- **Trámites informativos** en sede (Área Urbanismo): solicitud licencia urbanística (87), informe técnico (111/128), evaluación edificios (143), título habilitante (121), acceso expedientes (136).
- El tablón puede publicar notificaciones puntuales (p. ej. orden de ejecución de obras) pero no un registro sistemático de licencias.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SIT CM (`idem.madrid.org/cartografia/sitcm`) — planeamiento municipal (normas subsidiarias, ámbitos UE/APD) sin enlace a expediente concreto del ayuntamiento.
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO ILIKE '%San Lorenzo%'` + `DS_NOMB_AMB ILIKE '%hint%'`.
  - Ámbitos identificables en documentación: UE-9 La Tercera, UE-11 Cebadillas-Pozas, APD-3 Santa Clara, Las Pozas 145.
- **Estrategia:** tras extraer título del proyecto, buscar hints (`pozas`, `cebadillas`, `santa clara`, `ue-9`, `ue 11`, `pizarra`, `colonia`) en WFS SIT; rellenar `geom_geojson` cuando hay match.
- **Limitaciones:** tablón y PDFs sin georreferencia por expediente; visor SIT es regional (no REUR del ayuntamiento); licencias sin polígono; el orquestador aplicará centroide + jitter cuando no haya geometría.

## Limitaciones generales

- Tablón con pocas entradas activas en Urbanismo (1 anuncio evaluación edificios 2026).
- Transparencia con muchos PDFs históricos de planeamiento (fuente principal de proyectos).
- Sin listado público de licencias concedidas.
- Certificado digital para consulta de expedientes administrativos.
