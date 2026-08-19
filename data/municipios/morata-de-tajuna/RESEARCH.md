# Morata de Tajuña — investigación portal ayuntamiento

**Municipio:** Morata de Tajuña (Comunidad de Madrid)  
**Fecha:** 2026-08-10  
**BOCM regional (referencia):** 5 avisos

## Resumen

Morata de Tajuña publica información urbanística en la **web municipal Joomla** (`ayuntamientodemorata.es`)
y el **tablón de anuncios** de la sede electrónica espublico gestiona (`ayuntamientodemorata.sedelectronica.es`).
Los ámbitos de planeamiento están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.ayuntamientodemorata.es` | Joomla Purity III | Concejalías, bandos, noticias |
| Urbanismo | `https://www.ayuntamientodemorata.es/concejalias/urbanismo` | HTML + PDFs | Formularios licencia, DR, cédula, vado, terrazas |
| Bandos | `https://www.ayuntamientodemorata.es/bandos` | Joomla artículos | ~53 bandos (1 sobre ordenanza vallados SNU) |
| Sede electrónica | `https://ayuntamientodemorata.sedelectronica.es` | espublico gestiona | Tablón, transparencia |
| Tablón de anuncios | `https://ayuntamientodemorata.sedelectronica.es/board` | HTML tabla | ~10 anuncios/página (presupuesto, empleo, corporación) |
| Transparencia | `https://ayuntamientodemorata.sedelectronica.es/transparency/` | HTML | Portal transparencia (sin sección urbanismo explícita) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 23 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='MORATA DE TAJUÑA'` |

## Cómo se listan expedientes

- **Tablón sede:** Tabla HTML espublico con columnas Documento/Expediente/Procedimiento/Categoría/Descripción/Fecha.
  Actualmente sin anuncios de urbanismo recientes (mayoría presupuesto/empleo/corporación).
- **Web urbanismo:** Página estática con enlaces a PDFs de solicitud de licencia, declaración responsable,
  cédula urbanística, ocupación de vía, vado, terraza, etc. Dos noticias con documentación requerida.
- **Bandos:** Listado Joomla paginado; incluye bando sobre redacción de ordenanza de vallados en suelo no urbanizable.
- **No hay** visor urbanístico propio, catálogo `/dossier` ni API JSON de expedientes en la sede.
- `/dossier` redirige; `/catalog` devuelve 404.

## Licencias

- Trámites informativos en concejalía urbanismo: formularios PDF y noticias 977/978 (documentación licencia/DR).
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecerían en tablón sede cuando se publiquen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='MORATA DE TAJUÑA'` (`srsName=EPSG:4326`)
  - 23 ámbitos: UA-1 a UA-25 (con huecos), SECTOR INDUSTRIAL, SECTOR RESIDENCIAL
  - Visor SIT CM: `https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente/sistema-informacion-territorial-visor-sit`
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson`; enriquecer proyectos del tablón/bandos cuando el título contiene código UA o sector.
- **Limitaciones:** PDFs sin georreferenciación; tablón sin geometría; no hay visor municipal propio; transparencia sin listado de expedientes.

## Limitaciones

- Tablón con pocos anuncios urbanísticos (mayoría administración general).
- Licencias solo como páginas de trámite/formularios, sin concesiones publicadas con coordenadas.
- Ámbitos SITCM sin enlace directo a expediente del ayuntamiento.
- Dominios alternativos (`moratadetajuna.es`, `ayto-moratadetajuna.sedelectronica.es`) no resuelven o son genéricos.

## Estrategia adapter

1. Semillas de ámbitos SIT WFS (23 figuras) con `geom_geojson`.
2. Extraer PDFs y noticias de `/concejalias/urbanismo`.
3. Filtrar bandos con contenido urbanístico.
4. Parsear tablón sede espublico (anuncios urbanismo/licencias cuando aparezcan).
5. Páginas informativas de trámites de licencia.
6. IDs: `morata-de-tajuna-{lic|proy}-{sha256[:14]}`.
