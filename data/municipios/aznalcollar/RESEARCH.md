# Aznalcóllar — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `aznalcollar` |
| INE | 41013 |
| CIF | P4101300D |
| CMS web | OpenCMS INPRO (`es.inpro.opencms.*`) |
| Sede | GSede Diputación Sevilla (`sedeaznalcollar.dipusevilla.es`) |
| Boletín | BOJA (`boja`) |

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.aznalcollar.es |
| Sede GSede (Dip. Sevilla) | https://sedeaznalcollar.dipusevilla.es |
| Tablón INPRO provincial | https://sedeaznalcollar.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41013 |
| Tablón web municipal | https://www.aznalcollar.es/es/ayuntamiento/Tablon-Anuncios/ |
| LicytalPub licencias | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4101300D |
| Sede espublico | https://aznalcollar.sedelectronica.es (indeterminada — sin board) |
| Sitemap | https://www.aznalcollar.es/sitemap.xml |

### Semillas urbanismo (PDFs y anuncios)

- PGOU aprobación inicial: noticia + tablón web (`Bando-Aprobacion-inicial...`, `Aprobacion-inicial-del-Plan-General...`)
- PE Parque Mirador (consulta pública 2026): tablón web con PDFs en `.galleries/documentos-entidades/`
- Ordenanza ocupación espacios públicos / ordenanzas municipales (noticias)
- Ordenanza contaminación acústica (tablón web)
- Agenda Urbana 2022-2030 (noticia)
- Transparencia PGOU/modificaciones (indicador ITA — página mayormente vacía)

## Cómo se listan expedientes

### Web OpenCMS INPRO

- Noticias y tablón de anuncios web con HTML estático.
- Documentos en galerías OpenCMS: `/export/sites/aznalcollar/.galleries/documentos-noticias/*.pdf`, `documentos-entidades/*.pdf`.
- El sitemap XML lista URLs históricas de noticias y tablón; el adapter filtra por keywords urbanísticas.

### Tablón INPRO (Diputación Sevilla)

- Formulario HTML con tabla `celdaGrid` + campos ocultos (`referencia`, `asunto`, URL documento).
- Codificación `latin-1`. Categoría "Urbanismo" disponible en filtro pero pocos registros activos (4 en sept. 2026).
- Sin geometría ni API JSON.

### Licencias de obra

- No hay listado público de licencias concedidas en la web ni en el tablón INPRO actual.
- Trámites vía sede GSede (ticket por área, sin listado scrapeable).
- LicytalPub (`P4101300D`) es portal provincial de licencias/consulta (enlace informativo).
- Sede espublico gestiona responde "seleccione su sede" — no operativa para scraping.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal público. SITUA/JCyL (ws132.juntadeandalucia.es) es interfaz JSF sin WFS por expediente enlazable. PDFs del PGOU/PE son documentos sin georreferencia embebida.
- **Estrategia:** Centroide municipal INE `[37.5231, -6.2699]` + jitter vía orquestador `geocode`.
- **Limitaciones:** Sin ArcGIS/WFS/GeoJSON municipal; expedientes solo como PDFs y anuncios textuales.

## Limitaciones

- Tablón INPRO con muy pocos edictos vigentes; contenido urbanístico principalmente en web/tablon-anuncios histórico.
- Sede espublico no configurada (página indeterminada).
- Indicadores transparencia ITA devuelven plantilla vacía en varios endpoints.
- Sin coordenadas ni polígonos por expediente.
