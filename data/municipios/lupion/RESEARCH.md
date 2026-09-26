# Lupión — investigación portal ayuntamiento

**Municipio:** Lupión (Jaén, Andalucía)  
**Slug:** `lupion`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 23062

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lupion.es | **Operativa** — WordPress Colibri; orientada a turismo |
| Sede electrónica | https://lupion.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://lupion.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Catálogo trámites | https://lupion.sedelectronica.es/dossier | **Operativa** (requiere `insecure_ssl`) |
| Portal transparencia | https://lupion.sedelectronica.es/transparency | **Operativa** — sin carpetas urbanismo estructuradas |
| Normativa | https://lupion.sedelectronica.es/normative | Redirección circular (302) |
| Consulta expedientes | https://lupion.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| SITUA / VITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional Jaén (código 23062) |

## Web municipal (WordPress)

- CMS: WordPress + Colibri Page Builder.
- Secciones: turismo, patrimonio, fiestas, datos generales, Guadalimar.
- **Sin sección de urbanismo** ni PDFs de planeamiento en el sitio.
- Enlace destacado a sede electrónica desde cabecera y página Ayuntamiento.
- API REST (`/wp-json/wp/v2/pages`) sin páginas de urbanismo; 0 posts publicados.

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cómpeta, Lepe, Antas.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Contenido actual (sep 2026):** ~10 filas; mayoría subvenciones, empleo, IAE. Sin licencias de obra ni planeamiento en primera página.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites informativos en catálogo sede (`/dossier`):
  - Declaración Responsable o Comunicación en Materia Urbanística
  - Solicitud de Licencia o Autorización Urbanística
  - Solicitud de Licencia de Actividad
  - Solicitud de Licencia de Ocupación
  - Solicitud de Certificado o Informe Urbanístico
- Las licencias concedidas se publican en el tablón como edictos (cuando existan).

## Proyectos / planeamiento

- **Tablón:** sin anuncios de planeamiento en primera página (sep 2026).
- **SITUADIFUSION:** consulta del planeamiento urbanístico de Andalucía para municipio 23062 (Lupión, Jaén). Sin visor propio del ayuntamiento.
- **Transparencia sede:** portal genérico espublico; sin registro de instrumentos de ordenación estructurado.
- No hay visor de seguimiento de expedientes público fuera del tablón.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA/VITUA (Junta de Andalucía): planeamiento regional digitalizado; sin enlace por expediente del ayuntamiento.
  - IDEAndalucía WFS (`https://www.ideandalucia.es/services/wfs`): servicio genérico; sin capa municipal enlazada a expedientes del tablón.
  - Web municipal: sin visor urbanístico ni datos abiertos georreferenciados.
- **Estrategia:** los visores regionales muestran zonificación PGOU, **sin campo de enlace a expediente** del tablón. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON por código de expediente.
  - `/normative` con redirección circular.
  - El orquestador aplicará centroide municipio + jitter para coordenadas.

## Limitaciones generales

- Web sin contenido urbanístico; toda la gestión vía sede electrónica.
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Sin geometría por expediente.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.lupion:LupionAyuntamientoAdapter`
- Fuentes: tablón sede + catálogo trámites urbanismo (`/dossier`) + consulta SITUADIFUSION (planeamiento regional).
