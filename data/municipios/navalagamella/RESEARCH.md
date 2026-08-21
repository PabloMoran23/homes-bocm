# Navalagamella — investigación portal ayuntamiento

**Municipio:** Navalagamella (Comunidad de Madrid)  
**Fecha:** 2026-08-21  
**BOCM regional (referencia):** 3 avisos

## Resumen

Navalagamella publica trámites y noticias en la **web corporativa** `aytonavalagamella.es` (Hostinger Website Builder / Astro + assets Zyrosite) y anuncios oficiales en la **sede electrónica espublico gestiona** (`aytonavalagamella.sedelectronica.es`). No hay visor urbanístico municipal propio; la delimitación de ámbitos de planeamiento está disponible de forma indirecta en el **WFS SITCM** de la Comunidad de Madrid.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://aytonavalagamella.es` | Astro SPA (Zyrosite) | Áreas urbanismo, trámites licencias, notas de pleno, noticias |
| Área Urbanismo | `https://aytonavalagamella.es/area-de-urbanismo` | HTML | Enlaces a trámites licencias y calificaciones |
| Área Urbanizaciones | `https://aytonavalagamella.es/area-de-urbanizaciones` | HTML | Noticias obras/urbanizaciones (p. ej. Hotel Cerro Alarcón) |
| Información pública | `https://aytonavalagamella.es/solicitud-informacion-publica` | PDF Zyrosite | Formulario acceso IP |
| Tablón de anuncios | `https://aytonavalagamella.sedelectronica.es/board/` | HTML tabla Wicket | Edictos oficiales (licencias, empleo, etc.) |
| Portal transparencia | `https://aytonavalagamella.sedelectronica.es/transparency/` | Wicket | Enlaces tablón y consulta expedientes |
| Consulta expedientes | `https://aytonavalagamella.sedelectronica.es/expedientes` | Cl@ve / SAML | Requiere autenticación |
| Trámites sede | `https://aytonavalagamella.sedelectronica.es/dossier` | Wicket | Catálogo trámites (redirect en algunos entornos) |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

En agosto 2026 el tablón muestra principalmente convocatorias de empleo (exp. 322/2026); los anuncios de urbanismo aparecen de forma intermitente. El adapter filtra filas por palabras clave de licencias/urbanismo.

## Licencias

- Páginas informativas de trámites en web: licencia obra mayor, actuación comunicada, calificaciones urbanísticas, certificados urbanísticos.
- Anuncios de concesión/exposición pública en tablón sede cuando procedimiento = *Licencias Urbanísticas*.
- No hay dataset abierto de licencias con coordenadas.
- Consulta de expedientes en sede requiere Cl@ve.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `sitcm:VPLA_V_AMBITO` filtrado `DS_MUNICIPIO='NAVALAGAMELLA'` (17 ámbitos P-01…P-17, plan parcial / suelo reserva urbana).
- **Estrategia:** Tras extraer metadatos del expediente, consultar WFS por código de ámbito (`P-XX`) o coincidencia ILIKE en `DS_NOMB_AMB`; rellenar `geom_geojson` en WGS84.
- **Limitaciones:** Sin visor ArcGIS municipal; tablón y notas de pleno son PDF/HTML sin georreferencia directa; geometría solo enlazable cuando el título menciona un ámbito SITCM.

## Limitaciones

- `www.navalagamella.es` no resuelve; dominio activo es `aytonavalagamella.es`.
- Certificado SSL sede: adapter usa `insecure_ssl: true`.
- Tablón muestra ~9 anuncios recientes; histórico requiere búsqueda Wicket POST (no implementado).
- `/dossier` puede devolver redirect loop en CI.
- Web Astro: contenido renderizado con mucho JS embebido; el adapter parsea título, fecha y PDFs del HTML.

## Estrategia adapter

1. Scrape tabla tablón `/board/` (espublico).
2. Crawl semillas web: áreas urbanismo/urbanizaciones, trámites licencias, notas de pleno y noticias filtradas del sitemap.
3. Páginas informativas de licencias (referencia tablón + trámites).
4. Enriquecimiento geometría vía WFS SITCM cuando el título contiene código P-XX.
5. IDs estables: `navalagamella-{lic|proy}-{sha256[:14]}`.

## Referencia adapters

- Tablón espublico: `humanes_de_madrid.py`, `brunete.py`
- WFS SITCM Madrid: `valdemorillo.py`, `becerril_de_la_sierra.py`, `venturada.py`
