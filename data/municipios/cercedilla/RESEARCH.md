# Cercedilla — investigación portal ayuntamiento

**Slug:** `cercedilla`  
**Nombre oficial:** Cercedilla  
**BOCM (referencia):** 11 anuncios  
**Fecha investigación:** 2026-08-02

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web institucional (WordPress) | https://cercedilla.es | Accesible |
| Sede electrónica (eAdministración Maggioli) | https://sederecaudacioncercedilla.eadministracion.es | Parcial (tablón no accesible) |
| Visor SIT CM (Comunidad de Madrid) | https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm | Accesible |

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Departamento de Urbanismo | `/departamento-de-urbanismo/` | WordPress + PDFs | Ordenanzas, modelos licencia (DOC_*), BOCM urbanismo, tasas |
| Avance PGOU | `/avance-plan-general-ordenacion-urbana-cercedilla/` | WordPress + PDFs | Documentación avance PGOUC (memorias, planos, estudios ambientales) |
| Anuncios oficiales | `/anuncios-oficiales/` | WordPress + PDFs | Tablón web histórico (~640 PDFs; filtro urbanismo/licencias) |
| Sede electrónica | `sederecaudacioncercedilla.eadministracion.es` | ASP.NET eAdmin | Registro y trámites; tablón redir=13 devuelve error de sesión |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO` | GeoJSON WFS | 9 ámbitos UA-SU / SAU del municipio |

## Estructura web

- CMS WordPress con documentación en rutas `/DOCUMENTACION/urbanismo/` y `/DOCUMENTACION2/urbanismo/`.
- La página de urbanismo enlaza modelos de trámite (licencias obra mayor/menor, declaración responsable, parcelación, alineación, certificados urbanísticos).
- El avance PGOU (oct 2025 – ene 2026) publica bloques B1–B4 con volúmenes PDF y planos individuales (PI/PO/DIE); el adapter conserva volúmenes e índices, omitiendo láminas sueltas.
- REST API WordPress operativa para el post del avance PGOU (`/wp-json/wp/v2/posts?slug=...`).

## Licencias

No hay listado tabular público de concesiones con coordenadas.

Fuentes:

- Modelos PDF en sección urbanismo (DOC_1–DOC_24, formularios V2/V3/V4)
- Sede electrónica para presentación telemática (sin scrape de resoluciones)

## Proyectos / expedientes

- Avance PGOU Cercedilla (información pública 2025–2026)
- Publicaciones BOCM en `/DOCUMENTACION2/urbanismo/` (p. ej. BOCM-20250313-39)
- Estudio de detalle y convenios en anuncios oficiales
- Ordenanzas y normativa urbanística en web

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS SITCM `sitcm:VPLA_V_AMBITO` filtrado `DS_MUNICIPIO='CERCEDILLA'` (9 ámbitos: UA-SU-1…6, SAU-1 LAS FUENTES, SAU-2 NAVALCABALLO, SAU-3 LOS ARROYUELOS). Visor regional SIT CM enlazado desde la página de urbanismo.
- **Estrategia:** Tras scrape, consultar WFS por código UA-SU/SAU o palabras clave en título (p. ej. «MATALAVIEJA» → `UA-SU-2 MATALAVIEJA`). PGOU y PDFs genéricos no tienen polígono por expediente.
- **Limitaciones:** Sin visor municipal propio ni geometría por licencia; sede sin tablón scrapeable; matching por título es heurístico.

## Limitaciones

- Tablón sede (`/board`, `redir=13`) devuelve 404 o error de sesión
- Licencias: solo trámites/modelos informativos, sin registro público de concesiones
- Anuncios oficiales mezcla todo el tablón municipal; se filtra por palabras clave urbanísticas
