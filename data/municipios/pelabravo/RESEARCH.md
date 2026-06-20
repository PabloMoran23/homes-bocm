# Pelabravo — investigación portal ayuntamiento

**Municipio:** Pelabravo (Salamanca, Castilla y León)  
**Fecha:** 2026-06-20  
**BOCM regional (referencia):** 43 avisos

## Resumen

Pelabravo publica urbanismo y licencias principalmente en la **sede electrónica espublico gestiona**
(`pelabravo.sedelectronica.es`). La web corporativa `pelabravo.es` responde con *connection reset* desde
entornos automatizados (IP/CDN); la ingesta usa solo la sede.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://pelabravo.sedelectronica.es/board` | HTML tabla Wicket | Edictos, planeamiento, órganos de gobierno |
| Inicio (extracto tablón) | `https://pelabravo.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios publicados |
| Catálogo trámites | `https://pelabravo.sedelectronica.es/dossier.0` | HTML Wicket | Trámites urbanismo/licencias (`/catalog/t/{uuid}`) |
| Portal transparencia | `https://pelabravo.sedelectronica.es/transparency` | Wicket/AJAX | Sección 7 Urbanismo (326 docs; requiere expandir categoría) |
| Web municipal | `http://pelabravo.es` | — | **Bloqueado** (TCP reset en CI) |
| Noticias urbanismo | `http://pelabravo.es/noticias/...` | — | Inaccesible desde CI; referencia manual en COAL/BOCyL |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (jun 2026):

- Aprobación inicial Estudio de Detalle Sector MUR-A (Categoría: Urbanismo / Planeamiento General)
- Documentación modificación normas MUR-A (varios PDF)
- Convocatorias de pleno, bandos, modificaciones presupuestarias

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas (sin listado de concesiones):

- Licencia Urbanística, Declaración Responsable de Obra Menor
- Modificación del Planeamiento de Desarrollo, Planeamiento General (Modificación)
- Solicitud de Actuación Urbanística, Certificado/Informe Urbanístico
- Licencias de actividad, ocupación, etc.

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones (sin paridad Madrid `lat`/`lon`).

- Anuncios de licencia en tablón cuando se publican edictos.
- Páginas de trámite del catálogo sede como referencia informativa.

## Limitaciones

- `pelabravo.es`: inaccesible (connection reset) — no se usa como fuente.
- Certificado SSL sede: emisor Firmaprofesional no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0` y sesión `JSESSIONID`; tokens AJAX expiran (solo GET estático del tablón).
- Tablón muestra ~10 anuncios recientes por página; histórico requiere búsqueda POST Wicket (no implementado).
- Portal transparencia categoría Urbanismo carga documentos vía AJAX (`exp` links).

## Estrategia adapter

1. Scrape tabla tablón `/board` + extracto `/info.0`.
2. Catálogo trámites `/dossier.0` filtrado por keywords urbanismo/licencia.
3. IDs estables: `pelabravo-{lic|proy}-{sha256[:14]}`.
4. `source: ayuntamiento` en todos los registros.

## Referencia adapters

- Tablón HTML + regex títulos: `mostoles.py`, `rivas_vaciamadrid.py`
- SSL sede inseguro: `getafe.py`, `fuenlabrada.py`
