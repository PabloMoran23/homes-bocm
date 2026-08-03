# Mejorada del Campo — investigación portal ayuntamiento

**Municipio:** Mejorada del Campo (Comunidad de Madrid)  
**Fecha:** 2026-08-03  
**BOCM regional (referencia):** 10 avisos

## Resumen

Mejorada del Campo gestiona trámites y publicaciones en la **sede electrónica espublico gestiona**
(`mejoradadelcampo.sedelectronica.es`). Los ámbitos de planeamiento municipal están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`). La web corporativa Liferay
(`www.mejoradadelcampo.es`) no es accesible desde entornos cloud (conexión SSL reset).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Sede electrónica | `https://mejoradadelcampo.sedelectronica.es` | espublico gestiona | Trámites, tablón, transparencia |
| Tablón de anuncios | `https://mejoradadelcampo.sedelectronica.es/board` | HTML tabla | ~10 anuncios (contratación, urbanismo, empleo) |
| Catálogo trámites | `https://mejoradadelcampo.sedelectronica.es/dossier` | HTML catálogo | 19 trámites urbanismo/licencias/actividades |
| Transparencia | `https://mejoradadelcampo.sedelectronica.es/transparency` | Wicket | Portal transparencia (sin sección urbanismo explícita) |
| Web municipal | `https://www.mejoradadelcampo.es` | Liferay | **Inaccesible** (SSL connection reset desde cloud) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 25 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='MEJORADA DEL CAMPO'` |

## Cómo se listan expedientes

- **Tablón sede:** Tabla HTML espublico con columnas Documento/Expediente/Procedimiento/Categoría/Descripción/Fecha.
  Incluye anuncios de urbanismo (p. ej. «Aplicación régimen extraordinario incremento edificabilidad VPP»).
- **Catálogo trámites:** Enlaces a fichas de trámite (`/catalog/t/{uuid}`) para planeamiento, licencias y actividades.
- **No hay** visor urbanístico propio ni API JSON de expedientes en la sede.
- **Web municipal:** Presumiblemente secciones de urbanismo en Liferay, pero no scrapeable desde CI.

## Licencias

- Trámites informativos en catálogo sede: licencia de obra, actividad, ocupación, declaración responsable urbanística.
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón sede cuando se publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='MEJORADA DEL CAMPO'` (`srsName=EPSG:4326`)
  - 25 ámbitos: UE-2 a UE-20, API-1/2/3, S-1 a S-10 (planes parciales aplazados)
  - Visor SIT CM: `https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente/sistema-informacion-territorial-visor-sit`
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos del tablón cuando el título contiene código UE/S/API.
- **Limitaciones:** PDFs sin georreferenciación; web municipal inaccesible; tablón sin geometría; transparencia Wicket no automatizable.

## Limitaciones

- Web municipal `www.mejoradadelcampo.es` bloqueada (SSL reset) — no se pueden scrapear PDFs ni secciones Liferay.
- Tablón con pocos anuncios urbanísticos (mayoría contratación/empleo).
- Licencias solo como páginas de trámite, sin concesiones publicadas con coordenadas.
- Ámbitos SITCM sin enlace directo a expediente del ayuntamiento.

## Estrategia adapter

1. Parsear tablón sede espublico (anuncios urbanismo y licencias).
2. Extraer trámites urbanismo/licencias del catálogo `/dossier`.
3. Semillas de ámbitos SIT WFS (25 figuras) con `geom_geojson`.
4. Enriquecer geometría por código UE/S/API en título.
5. IDs: `mejorada-del-campo-{lic|proy}-{sha256[:14]}`.
