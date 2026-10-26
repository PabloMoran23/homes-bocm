# Plasencia — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `plasencia` |
| Provincia | Cáceres |
| CCAA | Extremadura |
| Web | https://www.plasencia.es/web/ (Joomla, plantilla Urbanus/Helix) |
| Sede | https://sede.plasencia.es (STA / T-Systems) |

## Fuentes

### Tablón de anuncios (principal)

- URL: `https://sede.plasencia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` (sin `KEY=all`; con `KEY=all` solo devuelve 5 filas)
- Formato: HTML con `var dataset_PTS2_TABLON = [...]` (JSON embebido).
- Remitentes urbanismo: `URBANISMO`, `URBANISMO-DISCIPLINA`.
- Detalle por anuncio: `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
- Contenido: modificaciones PGM, estudios de detalle, reparcelaciones, sanciones urbanísticas, etc.

### Catálogo de trámites (licencias)

- URL: `https://sede.plasencia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO`
- Dataset: `CATSERV` (mismos patrones STA que otros ayuntamientos).
- Trámites relevantes: Licencia de Obras, Comunicación Previa, Primera Ocupación, Proyecto de Urbanización, segregaciones, informe de compatibilidad urbanística.
- No publica concesiones concedidas; solo fichas de trámite.

### Transparencia — planeamiento (Joomla)

Semillas en menú **Desarrollo local → Urbanismo**:

| Página | URL |
|--------|-----|
| PGOU/PGM | `/web/portal-de-transparencia/materias-de-urbanismo-y-obras-publicas/plan-general-de-ordenacion-urbana` |
| Normativa | `.../normativa-urbanistica` |
| Plan Director Muralla | `.../plan-director-muralla-de-plasencia` |
| Plan Especial Intramuros | `.../plan-especial-de-proteccion-del-recinto-intramuros` |

PDFs bajo `/web/images/documentos/doc-urbanismo/` (modificaciones PGM2015, suelos municipales, etc.).

### Otros

- Ordenanzas: `PAGE_CODE=PTS2_ORDENANZA` en sede.
- Punto de información catastral (web corporativa).
- Catálogo suelos municipales (PDF en doc-urbanismo).

## Licencias

- **Listado público de concesiones:** no encontrado.
- **Estrategia adapter:** catálogo STA (trámites informativos) + filas del tablón que mencionan licencia/comunicación previa (pocas).

## Proyectos / expedientes

- Tablón STA filtrado por remitente urbanismo o texto de planeamiento.
- PDFs PGM en portal de transparencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** no hay visor urbanístico municipal público enlazado desde la web ni sede; PGOU solo en PDF/planos estáticos. IDE Extremadura (`ideextremadura.juntaex.es`) no expone capa de expediente enlazable al tablón en esta investigación.
- **Estrategia:** centroide municipal en `manifest.yaml` (`centroid: [40.0310, -6.0884]`) + jitter en geocode del orquestador.
- **Limitaciones:** referencias catastrales en anuncios de disciplina sin API GIS municipal; sin `geom_geojson` en adapter.

## Limitaciones

- Tablón mezcla disciplina urbanística con planeamiento; filtro por remitente/palabras clave.
- Muchos anuncios no urbanísticos (medio ambiente, jurados, tributos) excluidos por regex.
- SSL sede: certificado válido en pruebas; flag `sede_insecure_ssl` por consistencia con otros STA.
