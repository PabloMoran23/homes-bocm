# Prádena del Rincón — investigación portal ayuntamiento

**Municipio:** Prádena del Rincón (Comunidad de Madrid)  
**Fecha investigación:** 2026-08-11  
**Portal base:** https://pradenadelrincon.net

## Resumen

Prádena del Rincón publica normativa y trámites en su **web municipal WordPress Divi**
(`pradenadelrincon.net`) y gestiona expedientes en la **sede electrónica espublico gestiona**
(`pradenadelrincon.sedelectronica.es`). No hay sección dedicada de urbanismo; el contenido está
en normativa (ordenanzas), trámites (impresos licencias) y noticias del CMS.

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Web municipal | `https://pradenadelrincon.net` | WordPress Divi | Portal principal |
| Normativa | `https://pradenadelrincon.net/normativa/` | HTML + PDFs | Ordenanzas fiscales y urbanísticas (títulos habilitantes, licencias, IBI obras) |
| Trámites | `https://pradenadelrincon.net/tramites/` | HTML + PDFs | Licencia obra menor/mayor, declaración responsable |
| Bandos | `https://pradenadelrincon.net/bandos-y-anuncios-oficiales/` | WordPress | Enlace a sede y bandomovil |
| Transparencia | `https://pradenadelrincon.net/transparencia/` | WordPress | Portal transparencia |
| Sede electrónica | `https://pradenadelrincon.sedelectronica.es` | espublico gestiona | Trámites, expedientes, tablón |
| Tablón sede | `https://pradenadelrincon.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios (licitaciones/obras 2025-2026) |
| Bandomovil | `https://www.bandomovil.com/pradenadelrincon` | SPA Framework7 | Comunicados municipales (sin API pública) |
| Visor planeamiento | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=117` | ArcGIS/SITCM | Visor cartográfico CM |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | **3 ámbitos** UE-1, UE-2, UE-3 |

## Cómo se listan expedientes / proyectos

- **Normativa:** listado de PDFs de ordenanzas (24 documentos), incl. títulos habilitantes urbanísticos.
- **Posts WordPress:** noticias sobre desbroce de solares/parcelas, avisos limpieza solares.
- **API REST:** `https://pradenadelrincon.net/wp-json/wp/v2/posts?search=...`
- **Tablón sede:** tabla HTML con preview-document (licitaciones obras, expedientes contratación).
- **No hay** listado estructurado de expedientes de información pública ni visor con ficha por código.

## Cómo se publican licencias

- **No hay dataset** de licencias concedidas.
- Trámites informativos en `/tramites/`:
  - Licencia de obra menor (`Licencia-de-Obra-Menor.pdf`)
  - Licencia de obra mayor (`Licencia-de-Obra-Mayor.pdf`)
  - Declaración responsable de licencia
- Ordenanza tasa licencia apertura establecimiento en `/normativa/`.
- Trámites en sede (`/dossier`) requieren identificación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM (`idem.madrid.org/cartografia/sitcm/html/visor.htm?municipio=117`)
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='PRÁDENA DEL RINCÓN'` → **3 features** (UE-1, UE-2, UE-3)
- **Estrategia:** enriquecer proyectos cuyo título contiene código UE con polígono WFS; resto centroide + jitter
- **Limitaciones:** sin geometría por expediente individual; tablón/PDF sin enlace GIS; 3 UE genéricas en SITCM

## Limitaciones

- Tablón sede con licitaciones de obras, no licencias urbanísticas concedidas.
- Sin sección urbanismo dedicada; PGOU/NSS no publicados en web (consulta vía SITCM/CM).
- Bandomovil sin API scrapeable.
- SSL sede gestionado por espublico (adapter usa `insecure_ssl: true`).

## Patrón adapter

1. Crawl semillas WP (`normativa`, `tramites`, `bandos`, `transparencia`) + búsqueda REST API.
2. Parse enlaces PDF en normativa y trámites.
3. Tablón sede espublico (preview-document).
4. Licencias: páginas informativas de trámites (sin listado de concesiones).
5. Geometría: WFS SITCM por código UE en título.
6. IDs: `pradena-del-rincon-{lic|proy}-{sha256[:14]}`.
