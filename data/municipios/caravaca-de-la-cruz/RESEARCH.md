# Caravaca de la Cruz — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://caravacadelacruz.es | Urbanismo, normativa municipal, enlaces a sede |
| Urbanismo · Obras | https://caravacadelacruz.es/urbanismo-obras/ | Trámites (comunicación previa, certificado urbanístico, consultas) |
| Normativa municipal | https://caravacadelacruz.es/normativa-municipal/ | Normas y fichas, planimetría, plan general, PERIP, ordenanzas |
| Plan General | https://caravacadelacruz.es/plan-general/ | Documentación PGMO municipal |
| Sede Sedipualba | https://caravaca.sedipualba.es | Tablón de anuncios, catálogo de trámites |
| Tablón | https://caravaca.sedipualba.es/tablondeanuncios.aspx | Tabla HTML + RSS (`tablon_rss.aspx`) |
| Catálogo urbanismo | https://caravaca.sedipualba.es/catalogoservicios.aspx?area=887 | Trámite comunicación previa (`idtramite=11864`) |
| Transparencia | https://transparencia.caravacadelacruz.es | Información institucional (sin visor urbanístico propio) |

## Listado de expedientes / proyectos

- **Tablón Sedipualba:** filas HTML con enlace `anuncio.aspx?id=…`; RSS con últimos ~15 anuncios (iso-8859-1). Algún edicto de titularidad / exposición pública puede encajar como urbanismo.
- **Web normativa:** páginas semilla estáticas (plan general, normas y fichas, planimetría, PERIP avance) sin API JSON.
- No hay buscador público de expedientes urbanísticos enlazado a geometría.

## Licencias

- No hay registro público de licencias concedidas con ubicación.
- Trámite informativo en sede: comunicación previa en materia de urbanismo.
- Edictos de obra/licencia pueden aparecer esporádicamente en el tablón (filtro textual).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITMURCIA: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs` capa `plu_ze_37_mun_uso_suelo`, filtro `Municipio='Caravaca de la Cruz'` (~246 polígonos; campo `Ambito`, `Enlace_ficha` → opweb SITMURCIA).
  - Visor regional: https://sitmurcia.carm.es/planeamiento-urbanistico
- **Estrategia:** índice WFS en memoria; match por códigos de ámbito en título del anuncio; filas de referencia PGMO desde WFS con polígono completo.
- **Limitaciones:** WFS regional puede no reflejar el último PGMO municipal; tablón sin coords; licencias sin georreferencia; RSS acotado.

## Notas técnicas

- Sede Sedipualba (ASP.NET); tablón RSS en latin-1.
- INE municipio: **30008**.
- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
