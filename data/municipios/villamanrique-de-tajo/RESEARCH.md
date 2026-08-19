# Villamanrique de Tajo — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `villamanrique-de-tajo` |
| Web oficial | https://villamanriquedetajo.madrid |
| Sede electrónica | https://villamanriquedetajo.sedelectronica.es (espublico gestiona / eHome) |
| CMS web | WordPress (tema Bridge) |
| BOCM en pipeline | 5 entradas (`boletin_source_id: bocm`) |

## URLs base y páginas semilla

| Recurso | URL | Contenido |
|---------|-----|-----------|
| Inicio | https://villamanriquedetajo.madrid/ | Portal institucional WP |
| Normativa / PGOU | https://villamanriquedetajo.madrid/normativa-municipal/ | Plan General (aprob. BOCM 118/2016), capítulos PDF, planos, fichas ámbitos/sectores |
| Trámites | https://villamanriquedetajo.madrid/tramites-municipales/ | Licencia obra mayor, declaración responsable, primera ocupación, ocupación vía pública |
| Plenos | https://villamanriquedetajo.madrid/plenos/ | Actas y convocatorias (PDF) |
| Tablón sede | https://villamanriquedetajo.sedelectronica.es/board/ | Tablón de anuncios espublico (tabla HTML + preview-document) |
| Trámites sede | https://villamanriquedetajo.sedelectronica.es/dossier | Catálogo de procedimientos |
| Bandomóvil | https://www.bandomovil.com/villamanriquedetajo | Comunicados municipales (no urbanismo estructurado) |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Visor regional de planeamiento |

## Cómo se listan expedientes / proyectos

- **PGOU:** documentación estática en PDF enlazada desde `/normativa-municipal/` (plan completo, 11 capítulos, clasificación suelo, ordenación núcleo urbano, redes, catálogo bienes, inventario instalaciones, fichas ámbitos/sectores).
- **Tablón sede:** tabla HTML en `/board/` con columnas documento, expediente, procedimiento, categoría; enlaces `preview-document/`. En la fecha de investigación el tablón tenía muy pocos anuncios y ninguno claramente urbanístico.
- **No hay** visor urbanístico propio del ayuntamiento ni API JSON de expedientes.
- **Ámbitos de planeamiento:** publicados en el visor regional SITCM (WFS GeoServer Comunidad de Madrid).

## Cómo se publican licencias

- **No hay listado público** de licencias concedidas (sin dataset ni tablón de licencias).
- Formularios descargables en `/tramites-municipales/`:
  - `solicitud-licencia-obra-mayor-2021.pdf`
  - `declaracion_responsable-obra.pdf`
  - `solicitud-licencia-primera-ocupacion-2021.pdf`
  - `licencia-de-obras.pdf` (normativa)
  - `impreso-solicitud-ocupacion-via-publica.pdf`
- Presentación presencial o vía sede electrónica (`/dossier`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VILLAMANRIQUE DE TAJO'`
  - Campos: `DS_NOMB_AMB` (código ámbito: AA-1…AA-5, SUS-1 R…SUS-7 AE, AADA-1), `DS_FIG_DES`, geometría poligonal EPSG:4326
- **Estrategia:** descarga masiva de ámbitos PGOU vía WFS; enriquecimiento puntual por código de ámbito en títulos de documentos/tablon.
- **Ámbitos encontrados (14 polígonos, 13 nombres únicos):** AADA-1, AA-1, AA-2, AA-3, AA-4, AA-5 (×2 polígonos), SUS-1 R, SUS-2 R, SUS-3 R, SUS-4 R, SUS-5 AE, SUS-6 AE, SUS-7 AE.
- **Limitaciones:**
  - Licencias individuales sin georreferencia (solo formularios PDF).
  - Tablón sede con escasa actividad urbanística publicada.
  - PGOU en PDF sin geometría embebida; polígonos solo vía SITCM para ámbitos de planeamiento.
  - No hay enlace expediente→polígono en portal propio.

## Limitaciones generales

- Sin listado de licencias concedidas.
- Tablón de anuncios sede casi vacío de contenido urbanístico.
- SSL de sede funcional; `insecure_ssl` habilitado por consistencia con otros municipios espublico.
- Paginación del tablón sede no necesaria (pocos registros).

## Adapter implementado

- Módulo: `municipio/adapters/villamanrique_de_tajo.py`
- Proyectos: ámbitos SITCM WFS + PDFs PGOU de normativa municipal + tablón sede.
- Licencias: páginas informativas + formularios PDF de trámites + tablón sede.
