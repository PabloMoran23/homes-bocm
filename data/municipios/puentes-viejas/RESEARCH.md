# Puentes Viejas — investigación portal ayuntamiento

**Municipio:** Puentes Viejas (Comunidad de Madrid)  
**Fecha:** 2026-08-11

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://www.puentesviejas.org | Portal principal del ayuntamiento |
| Urbanismo | https://www.puentesviejas.org/urbanismo/ | Arquitecto municipal, cita previa |
| Tasas licencia obras | https://www.puentesviejas.org/tasas-licencia-de-obras-urbanas/ | Información tasas licencias |
| Títulos habilitantes urbanísticos | https://www.puentesviejas.org/tasa-por-expedicion-de-titulos-habilitantes-de-naturaleza-urbanistica/ | Tasas urbanísticas |
| Portal transparencia (WP) | https://www.puentesviejas.org/portal-de-transparencia/ | Enlaces a sede y perfil contratante |
| Noticias PGOU 2026 | https://www.puentesviejas.org/2026/03/25/publicacion-del-documento-de-avance-del-plan-general-de-ordenacion-urbana-de-puentes-viejas/ | Avance PGOU en tablón |
| Sede electrónica (espublico gestiona) | https://puentesviejas.sedelectronica.es/board | Tablón de anuncios |
| Transparencia sede | https://puentesviejas.sedelectronica.es/transparency | Documentación municipal (Wicket) |
| Catálogo trámites | https://puentesviejas.sedelectronica.es/dossier | Trámites (lento; incluye Declaración Responsable Urbanística) |

## Cómo se listan expedientes

- **WordPress:** noticias y páginas estáticas; REST API en `https://www.puentesviejas.org/wp-json/wp/v2/` (posts + pages).
- **Tablón sede:** HTML tabla con `preview-document` (espublico gestiona). Columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
- **PGOU:** documento de avance publicado en tablón (marzo 2026) + noticias en web corporativa con PDF modelo de sugerencias.
- No hay visor de expedientes individual ni API JSON de expedientes urbanísticos.

## Cómo se publican licencias

- No hay dataset ni listado histórico de concesiones de licencia de obra.
- El tablón actual no contiene licencias urbanísticas (empleo público, IAE).
- Trámite destacado en sede: «Declaración Responsable o Comunicación en Materia Urbanística» (presentación electrónica).
- Estrategia: páginas informativas (urbanismo, tasas licencias, tablón) + tablón cuando aparezcan anuncios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='PUENTES VIEJAS'`
  - Campo ámbito: `DS_NOMB_AMB` (7 polígonos de plan parcial: POLÍGONO 6–11, 14)
- **Estrategia:** query WFS por municipio; semillas `_collect_sit_ambitos()` para los 7 polígonos; matching por código en título cuando aparece «POLÍGONO N».
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Certificado SSL de la sede inválido → `insecure_ssl: true` en adapter.
  - `/dossier` y `/info` en sede con respuesta lenta (timeout 45s).
  - Transparencia Wicket no scrapeable.
  - Geometría solo para ámbitos SITCM (planes parciales); PGOU avance sin polígono publicado.

## Limitaciones generales

- Sede espublico requiere `insecure_ssl` (certificado no válido para verificación estándar).
- Tablón con pocas entradas no urbanísticas en el momento de la investigación.
- Mayoría de proyectos de planeamiento vienen de SIT WFS + noticias PGOU recientes.
