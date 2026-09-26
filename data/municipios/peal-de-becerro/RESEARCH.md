# Peal de Becerro — investigación portal ayuntamiento

**Municipio:** Peal de Becerro (Jaén, Andalucía)  
**Slug:** `peal-de-becerro`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 23066

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.pealdebecerro.es | **Operativa** — WordPress Colibri (plantilla DipuJaén `webaytos.dipujaen.es`) |
| Urbanismo | https://www.pealdebecerro.es/ayuntamiento/urbanismo/ | **Vacía** — listado dinámico Colibri: «No hay publicaciones de Urbanismo» |
| Sede electrónica | https://pealdebecerro.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://pealdebecerro.sedelectronica.es/board/ | **Operativa** — tabla HTML (~10 filas), preview-document |
| Obras y Urbanismo (transparencia) | https://pealdebecerro.sedelectronica.es/citizen-service/f30306de-0ffc-415f-9820-6802cd4aad98 | **Operativa** — info DR, licencias, comunicaciones previas, planeamiento |
| Portal transparencia | https://pealdebecerro.sedelectronica.es/transparency/ | **Operativa** — menú normativa y áreas |
| Catálogo trámites | https://pealdebecerro.sedelectronica.es/dossier | **Inestable** — timeout frecuente en CI |
| Cita previa | https://pealdebecerro.sedelectronica.es/citaprevia | **Inestable** — timeout en CI |
| Consulta expedientes | https://pealdebecerro.sedelectronica.es/expedientes | Requiere autenticación |

## Cómo se listan expedientes / proyectos

1. **Tablón sede (`/board/`):** tabla HTML espublico con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. En agosto 2026 no hay filas de planeamiento/licencias (solo subvenciones, personal, contrataciones).
2. **Web urbanismo:** categoría WP `Urbanismo` (id 139) con 0 entradas; listado Colibri vacío.
3. **Planeamiento vigente:** Normas Subsidiarias de Planeamiento Municipal (NNSS) aprobadas en 1997 (MIVAU). Modificaciones recientes publicadas en BOJA (p. ej. polígono industrial, expediente 1-211/04, BOJA 2024/93/58).
4. **Noticias web:** solo 3 posts (ninguno urbanístico).

## Cómo se publican licencias

- No hay dataset público de concesiones de obra con coordenadas.
- Página transparencia «Obras y Urbanismo» describe trámites de DR, licencias urbanísticas y comunicaciones previas (informativo).
- Las licencias concedidas, cuando se publican, aparecen en el tablón de anuncios como edictos/bandos.
- Consulta de expedientes requiere identificación en sede.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SITUADIFUSION (`https://ws132.juntadeandalucia.es/situadifusion/`) — consulta por municipio no estable vía URL directa; NNSS 1997 digitalizada parcialmente en Junta.
  - IDE Diputación de Jaén (`ide.dipujaen.es`) — WFS no accesible (404); excluye municipios grandes según documentación provincial.
  - Web municipal: sin visor urbanístico ArcGIS/WFS; callejero estático sin capas de expedientes.
  - Tablón/transparencia: documentos PDF sin georreferencia machine-readable.
- **Estrategia:** sin fuente GIS consultable por código de expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** cartografía de planeamiento en PDF/BOJA sin polígonos descargables; sede sin geometría; tablón paginado con Wicket AJAX.

## Limitaciones generales

- Sección urbanismo web vacía (migración DipuJaén sin contenido).
- `/dossier` y `/normative` con timeouts en entorno CI.
- Sin geometría por expediente.
- Histórico de licencias no publicado como listado estructurado.

## Adapter implementado

- `municipio.adapters.peal_de_becerro:PealDeBecerroAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas trámites + seeds planeamiento (NNSS/BOJA) + SITUA referencia.
- IDs: `peal-de-becerro-lic-*` / `peal-de-becerro-proy-*` (sha256[:14]).
