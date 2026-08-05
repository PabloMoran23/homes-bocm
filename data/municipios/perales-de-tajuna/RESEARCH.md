# Perales de Tajuña — investigación portal ayuntamiento

**Municipio:** Perales de Tajuña (Comunidad de Madrid)  
**Slug:** `perales-de-tajuna`  
**Fecha:** 2026-08-03  
**BOCM regional (referencia):** 10 avisos

## Resumen

Perales de Tajuña publica planeamiento en la **web corporativa Neosoft** (`ayto-peralestajuna.org`)
y anuncios administrativos en la **sede electrónica espublico gestiona**
(`ayto-peralestajuna.sedelectronica.es`). No hay visor urbanístico municipal propio; la geometría
de ámbitos del planeamiento está en el **SIT de la Comunidad de Madrid** (WFS público, código
municipio 110).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://www.ayto-peralestajuna.org` | Neosoft CMS | Área urbanismo, PDFs planeamiento |
| Urbanismo | `https://www.ayto-peralestajuna.org/paginas/urbanismo` | HTML + PDFs | NNSS 1977, PONP Valdeperales, avance PGOU |
| Tablón de anuncios | `https://ayto-peralestajuna.sedelectronica.es/board` | HTML tabla Wicket | Edictos, licencias, exposiciones públicas |
| Portal transparencia | `https://ayto-peralestajuna.sedelectronica.es/transparency/` | Wicket AJAX | Documentación administrativa |
| Trámites sede | `https://ayto-peralestajuna.sedelectronica.es/dossier` | espublico | Licencias, DR, cédulas (presentación) |
| Portal tributario | `https://sede.ayto-peralestajuna.org/` | eAdmin | Tributos (no urbanismo) |
| SIT Comunidad de Madrid | WFS `sitcm:VPLA_V_AMBITO` | GeoJSON | 22 ámbitos P-1…P-22 |
| Visor SITCM | `http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=110` | HTML | Enlace desde web urbanismo |

Dominios no operativos: `www.peralesdetajuna.es`, `peralesdetajuna.es` (sin respuesta DNS).

## Web corporativa — urbanismo

Página `/paginas/urbanismo` con:

- **Documento Avance del Plan General de Ordenación Urbana** (texto; sin PDF directo indexado)
- **NNSS 1977:** Memoria urbanística + Planos de ordenación (PDF en `/Ficheros/Documentos/`)
- **PONP Valdeperales de Arriba** (PDF)
- Botones de trámites → `sedelectronica.es/info.0` (DR, licencia obras, primera ocupación, cédula, certificado, informe)
- Enlace visor SITCM Comunidad de Madrid

## Tablón de anuncios (`/board`)

Tabla HTML responsive (espublico gestiona) con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (ago 2026):

- **Licencias Urbanísticas** — estación recarga ultrarrápida A-3 PK 35+325 (exp. 214/2025, información pública)
- Padrón, IAE, actas pleno históricas (excluidos o filtrados en adapter)

Paginación: botón Wicket AJAX «Mostrar más» (tokens de sesión; no implementado).

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia aparecen en tablón bajo procedimiento *Licencias Urbanísticas*.
- Trámites de presentación en sede (`/dossier`, `/info.0`); concesiones publicadas en tablón.
- Portal tributario (`sede.ayto-peralestajuna.org`) es independiente (eAdmin, solo tributos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows`
  — capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='PERALES DE TAJUÑA'`.
  22 ámbitos: P-1…P-22 (polígonos EPSG:4326).
- **Estrategia:** Enriquecer proyectos cuyo título mencione código de ámbito (P-*)
  vía query WFS; visor SITCM enlazado desde web pero sin API expediente→polígono.
- **Limitaciones:** Tablón sin georreferenciación; PDFs planeamiento sin coords embebidas;
  expedientes tras login Cl@ve; sin ArcGIS/GeoJSON en portal del ayuntamiento.

## Limitaciones

- Tablón muestra ~10 anuncios recientes; histórico requiere paginación Wicket.
- Avance PGOU referenciado en web sin PDF directo scrapeable.
- Todos los botones de trámite urbanismo apuntan a `info.0` genérico (misma URL).
- `dossier` requiere CookieJar y puede ser lento (timeout en entorno cloud).

## Estrategia adapter

1. Scrape PDFs planeamiento desde `/paginas/urbanismo`.
2. Scrape tabla tablón `/board` (parser `data-label`).
3. Páginas informativas de trámites urbanísticos (sede + urbanismo).
4. Geometría WFS SIT cuando el título contenga código P-*.
5. IDs estables: `perales-de-tajuna-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `torrejon_de_velasco.py`, `humanes_de_madrid.py`
- WFS SIT partial: `cobena.py`, `paracuellos_de_jarama.py`
