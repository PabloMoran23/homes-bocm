# Las Torres de Cotillas — investigación portal ayuntamiento

Municipio: **Las Torres de Cotillas** (`las-torres-de-cotillas`) — Murcia, Región de Murcia. INE **30043**. Sin boletín regional asociado en cola.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal) | https://www.lastorresdecotillas.es |
| Urbanismo | https://www.lastorresdecotillas.es/urbanismo |
| Información urbanística / impresos | https://www.lastorresdecotillas.es/informacion-urbanistica |
| Consultas públicas previas | https://www.lastorresdecotillas.es/normativa-en-fase-consulta-publica-previa |
| Datos abiertos | https://datosabiertos.lastorresdecotillas.es |
| Agenda Urbana | https://agendaurbanaltc.com/ |
| Sede electrónica (espublico gestiona) | https://lastorresdecotillas.sedelectronica.es |
| Tablón de anuncios | https://lastorresdecotillas.sedelectronica.es/board |
| Catálogo trámites | https://lastorresdecotillas.sedelectronica.es/dossier |
| Consulta expedientes (login) | https://lastorresdecotillas.sedelectronica.es/expedientes |
| Portal transparencia | https://lastorresdecotillas.sedelectronica.es/transparency |
| Planeamiento (G13) | https://lastorresdecotillas.sedelectronica.es/transparency/7cfea38d-ece8-4801-a2cc-9924f3449c8d/ |

## CMS y listado de expedientes

- **Web:** Drupal 9/10 (`/noticias`, menús Bootstrap). Urbanismo documentado en páginas estáticas; sin visor cartográfico propio.
- **Sede:** **espublico gestiona** (Wicket). Tablón `/board` con tabla responsive (`class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `preview-document/{uuid}`). Categoría **Urbanismo** con actuaciones (p. ej. aprobación inicial UA-E1 PGMO).
- **Transparencia G13:** subcarpetas APR (64), API (33), nuevos desarrollos PGMO (95) — navegación AJAX wicket; listado de títulos en HTML inicial de la carpeta padre.
- **Expedientes:** `/expedientes` requiere identificación; no hay API pública de listado.

## Licencias

- No hay registro histórico abierto de licencias concedidas.
- Edictos puntuales en tablón si el ayuntamiento publica licencias/obras (filtro por palabras clave).
- Trámites: catálogo `/dossier` + impresos en `/informacion-urbanistica`.
- El adapter incluye filas informativas: tablón, dossier, expedientes, transparencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM: `https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs` — capa `plu_ze_37_mun_uso_suelo`, filtro `Municipio='Las Torres de Cotillas'` → **0 features** (nov 2026; CARM anuncia carga IDERM/INSPIRE en 1S2026).
  - Visor regional SITMURCIA / IDERM — planeamiento informativo, sin enlace estable expediente→polígono.
- **Estrategia:** Consulta WFS y cruce de códigos `U.A.-*` / `UA-*` en título del tablón si aparecen ámbitos en el futuro. Centroide municipal en manifest hasta entonces.
- **Limitaciones:**
  - Sin polígonos por expediente en fuentes abiertas actuales.
  - Tablón y transparencia son PDFs/anuncios sin georreferencia embebida.
  - Subcarpetas de planeamiento en transparencia requieren sesión wicket para paginar documentos.
