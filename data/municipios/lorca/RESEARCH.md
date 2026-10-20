# Lorca — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.lorca.es | Enlaces a sede y área de Urbanismo |
| Sede electrónica (Liferay) | https://www.portalciudadano.lorca.es | Tablón de anuncios, catálogo de trámites |
| Tablón de edictos | https://www.portalciudadano.lorca.es/web/guest/tablon-de-anuncios | Tabla HTML (título, descripción, fecha); detalle `/tablon-de-anuncios/anuncio/{id}/` |
| Catálogo trámites | https://www.portalciudadano.lorca.es/web/guest/catalogo-de-servicios | Trámites urbanísticos (p. ej. URMPGM, USTREC) |
| Concejalía Urbanismo | https://urbanismo.lorca.es | PGMO, modificaciones, planos PEPRI/PGOU (PDF y ASP) |
| Plan General | https://urbanismo.lorca.es/planGeneral.asp | Modificaciones estructurales y documentación PGMO |
| Planes parciales / especiales | https://urbanismo.lorca.es/planParcial.asp , planEspecial.asp | Enlaces a expedientes y PDFs |
| Datos abiertos | https://datos.lorca.es | Mapas OSM; sin enlace directo expediente↔geometría |

## Listado de expedientes / proyectos

- **Tablón sede:** filas en `<table>` servidas en SSR (sin API JSON pública). Paginación mediante enlace `siguiente` (`?page=N&...`); el histórico completo no está en la primera página.
- **Urbanismo web:** listados estáticos ASP con enlaces a PDFs de modificaciones del PGMO, planes parciales/especiales y PEPRI.
- Los anuncios de urbanismo incluyen metadatos en descripción (`EXPEDIENTE:`, `PROMOTOR: ÁREA DE URBANISMO`).

## Licencias

- No hay dataset público de licencias concedidas con coordenadas.
- Edictos de licencia/obra pueden aparecer en el tablón (filtro textual).
- Catálogo sede expone trámites informativos: recepción de obras de urbanización (`USTREC`), modificación PGMO (`URMPGM`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITMURCIA planeamiento general: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` con `Municipio='Lorca'` (~745 polígonos, campo `Ambito` p. ej. `UA-23`).
  - Visor regional IDERM (datos PG vigente ~dic. 2009 para Lorca): https://sitmurcia.carm.es/planeamiento-urbanistico
  - Visor sísmico municipal (no planeamiento): http://213.0.108.11/SeismoLorca/
- **Estrategia:** tras scrape, extraer códigos `UA-NN` / sector del título y consultar índice WFS en memoria; rellenar `geom_geojson` cuando hay match.
- **Limitaciones:** WFS regional desactualizado respecto al PGMO municipal; tablón sin geometría; licencias sin georreferencia; paginación del tablón limitada en entorno cloud.

## Notas técnicas

- `urbanismo.lorca.es` responde en **latin-1** (decodificar explícitamente).
- Sede Liferay usa URLs relativas `/tablon-de-anuncios/...` bajo `/web/guest/`.
- INE municipio: **30024**.
