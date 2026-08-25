# Pelayos de la Presa — investigación portal ayuntamiento

**Municipio:** Pelayos de la Presa (Comunidad de Madrid)  
**Fecha:** 2026-08-22  
**BOCM regional (referencia):** 3 avisos

## Resumen

Pelayos de la Presa publica normativa urbanística y formularios de licencias en web Joomla (`pelayosdelapresa.es`) y anuncios en sede electrónica espublico gestiona (`pelayospresa.sedelectronica.es`). No dispone de visor urbanístico propio; el planeamiento vigente se consulta en el registro de documentos urbanísticos de la Comunidad de Madrid (enlace desde ayuda-ciudadana).

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web principal | `https://www.pelayosdelapresa.es` | Joomla HTML | Ordenanzas, trámites |
| Ordenanzas reguladoras | `.../ayuntamiento/normativa-municipal/ordenanzas-reguladoras` | PDF en `/images/articulos/` | Ordenanzas urbanísticas |
| Trámites solicitudes | `.../tramites/solicitudes` | PDF impresos | Licencias (formularios) |
| Ayuda ciudadana | `.../ayuda-ciudadana` | HTML | Enlace planeamiento CM |
| Tablón sede | `https://pelayospresa.sedelectronica.es/board/` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Transparencia sede | `https://pelayospresa.sedelectronica.es/transparency/` | Wicket árbol | Sección 7 urbanismo (2 docs) |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UA con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='PELAYOS DE LA PRESA'`) |

## Fuentes detalladas

### 1. Web corporativa — Joomla

- **URL:** `https://www.pelayosdelapresa.es`
- **CMS:** Joomla (robots.txt confirma instalación en subcarpeta migrada a raíz).
- **Limitación:** Certificado SSL caducado (ago 2026); adapter usa `insecure_ssl: true`.
- **Secciones relevantes:**
  - `/ayuntamiento/normativa-municipal/ordenanzas-reguladoras` — ordenanzas de limpieza/vallado parcelas, residuos construcción, arbolado, licencias urbanísticas.
  - `/tramites/solicitudes` — impresos: solicitud licencia urbanística, declaración responsable, cédula urbanística.
  - `/ayuda-ciudadana` — enlace a registro documentos urbanísticos CM (buscar municipio "Pelayos de la Presa").

### 2. Sede electrónica espublico gestiona — Tablón de anuncios

- **URL:** `https://pelayospresa.sedelectronica.es/board/`
- **CMS:** espublico gestiona (Wicket/YUI).
- **Formato:** Tabla Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.
- **Estado ago 2026:** 6 anuncios vigentes; comunicaciones urbanísticas (arbolado suelo urbano, expediente 2401/2026).
- **Limitación:** Solo anuncios vigentes; sin histórico indexable ni paginación pública.

### 3. Portal de transparencia sede

- **URL:** `https://pelayospresa.sedelectronica.es/transparency/`
- **Sección 7:** URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE (2 documentos).
- **Acceso:** Árbol Wicket con AJAX; documentos en subcarpetas UUID.

### 4. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='PELAYOS DE LA PRESA'`
- **Ámbitos detectados (51):** UA-5, UA-8, UA-10, UA-11, UA-47, etc. (unidades de actuación y calificaciones)
- **Campos:** `DS_NOMB_AMB`, `DS_CLAS_SUE`, geometría polígono EPSG:4326
- **Planeamiento documental:** Registro CM (NNSS, modificaciones, planes parciales) vía ayuda-ciudadana

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `pelayosdelapresa.es` sin www | Redirige a www; mismo certificado caducado |
| Sede `/dossier` | Redirect loop (302) |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede individual | Requiere identificación Cl@ve |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='PELAYOS DE LA PRESA'`
  - Campo ámbito: `DS_NOMB_AMB` (UA-5, UA-8, UA-10, …)
  - Visor público: `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **Estrategia:** Descargar polígonos WFS por ámbito UA; cruzar títulos de anuncios con código UA cuando aparece en el texto.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS por expediente individual.
  - PDFs ordenanzas/impresos sin georreferencia embebida; geometría solo para ámbitos del planeamiento vigente en SITCM.
  - Tablón actual con pocos expedientes urbanísticos vigentes.
  - Web municipal con certificado SSL caducado.

## Limitaciones generales

- Municipio pequeño (~2.500 hab.) junto al embalse de San Juan.
- Publicación urbanística concentrada en ordenanzas PDF y registro CM.
- Tablón sede solo muestra anuncios vigentes.
- Licencias: formularios descargables, sin listado de concesiones con coordenadas.
