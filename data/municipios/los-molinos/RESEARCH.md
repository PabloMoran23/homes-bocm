# Los Molinos — investigación portal ayuntamiento

**Slug:** `los-molinos`  
**Nombre oficial:** Los Molinos  
**BOCM (referencia):** 15 anuncios  
**Fecha investigación:** 2026-07-23

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web institucional (WordPress) | https://www.ayuntamiento-losmolinos.es | Accesible |
| Sede electrónica (eAdmin/add4u) | https://sede.ayuntamiento-losmolinos.es/eAdmin | Accesible |
| Transparencia (WordPress) | https://transparencia.ayuntamiento-losmolinos.es | Accesible |
| Visor SIT CM (Comunidad de Madrid) | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm | Accesible |

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo (WP) | `/?page_id=36668` | WordPress + PDFs | NNSS 1991, PGOU planos, modelos licencia, normativa |
| Avance PGOU 2026 | `/?p=40276` | WordPress + PDFs | Presentación, formulario sugerencias, clasificación suelo |
| Avance PGOU (histórico) | `/?p=10954` | WordPress + PDFs | Bloques BQ.1–BQ.3 del avance (2018–2019) |
| Tablón edictos | `/eAdmin/Tablon.do?action=verAnuncios` | HTML tabla eAdmin | 19 anuncios vigentes; 6 bloques Avance PGOU (jun 2026) |
| Búsqueda tablón | POST `Tablon.do?action=verAnuncios` + `referenciaBusqueda` | HTML tabla | Filtrado por palabra clave |
| Detalle anuncio | `/eAdmin/Tablon.do?action=verAnuncio&id={hex}` | HTML | Periodo publicación, PDF original |
| PDF documento | `/eAdmin/ValidarDocumento.do?id_Documento={token}&tipo=doc&mode=ori` | PDF | Documento del edicto |
| Catálogo trámites | `/eAdmin/Registrar.do?action=listadoEntradas` | HTML modales | Licencias obra mayor/menor, DR actividad |
| Planeamiento (transparencia) | `/?page_id=185` | WordPress + `abrir('{token}')` | Estudio de detalle Finca La Cerquilla |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO` | GeoJSON WFS | 12 ámbitos UA/SAU del municipio |

## Estructura HTML tablón

Plataforma eAdmin (misma familia que Galapagar/Colmenar). Tabla con filas:

1. Iconos: `abrirOriginal('{token}')` (PDF) y `verAnuncio&id={id}` (detalle)
2. Título
3. Periodo: `DD/MM/YYYY - DD/MM/YYYY`

Ejemplos vigentes (jul 2026):

- `AVANCE PLAN GENERAL- ANUNCIO EXPOSICIÓN PÚBLICA BOCM`
- Bloques I–IV del avance PGOU + índice

## WordPress — urbanismo

Sección urbanismo publica ~38 PDFs: normas subsidiarias, planos PGOU (P1–P5), memoria, modificaciones, modelos de licencia (obra mayor/menor, comunicación previa, primera ocupación).

## Transparencia — planeamiento

`page_id=185` enlaza documentación vía `javascript:abrir('{token}')` hacia la sede:

- Estudio de detalle Finca La Cerquilla

## Licencias

No hay listado tabular de concesiones con coordenadas.

Fuentes:

- Modelos PDF en web urbanismo (informativos)
- Catálogo trámites sede: tipoReg 34–37, 51 (obra mayor/menor, DR actividad, plusvalía)

## Proyectos / expedientes

- Avance PGOU 2026 (tablón + WP)
- Documentación histórica avance PGOU 2018–2019 (WP)
- NNSS y planos PGOU en sección urbanismo
- Estudio de detalle en transparencia

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SITCM `sitcm:VPLA_V_AMBITO` filtrado `DS_MUNICIPIO='LOS MOLINOS'` (12 ámbitos: UA-01 La Cerquilla, SAU-01.N Los Arroyuelos, etc.). Visor regional SIT CM enlazable desde cartografía CM.
- **Estrategia:** Tras scrape, consultar WFS por código UA/SAU en título o tokens del nombre (p. ej. «CERQUILLA» → `UA-01 LA CERQUILLA`). Los avances PGOU y PDFs sin código de ámbito no tienen polígono enlazable.
- **Limitaciones:** Sin visor municipal propio; tablón y WP publican PDFs sin georreferencia; matching por título es heurístico (solo filas con código/nombre de ámbito SITCM).

## Limitaciones

- REST API WordPress deshabilitada (`/wp-json/` → 404)
- Tablón muestra anuncios **vigentes**; histórico vía búsqueda por términos
- Licencias: solo trámites/modelos informativos, sin registro público de concesiones
