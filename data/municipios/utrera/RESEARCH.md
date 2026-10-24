# Utrera — investigación portal ayuntamiento

**Slug:** `utrera`  
**Comunidad:** Andalucía (provincia Sevilla)  
**INE:** 41095 | **CIF Licytal:** P4109500I

## URLs base y semillas

| Fuente | URL | Formato |
|--------|-----|---------|
| Web municipal | https://www.utrera.org | WordPress (tema Extra), CPT `project` |
| Área urbanismo (WP) | https://www.utrera.org/project_category/urbanismo-vivienda-y-patrimonio/ | HTML + REST `/wp-json/wp/v2/project` |
| PGOU 2015 (documentos) | https://www.utrera.org/documento-pgou-aprobacion-provisional-3a-.../ | PDFs en `/wp-content/uploads/2018/06/` |
| PGOU 2002 | http://www.utrera.org/pgou2002/ | Índice PDF PGOU histórico |
| Transparencia | https://transparencia.utrera.org/ | WordPress Divi |
| PGOU transparencia | https://transparencia.utrera.org/project/plan-general-de-ordenacion-urbana-pgou-y-los-mapas-y-planos-que-lo-detallan/ | Enlace a documento PGOU 2015 |
| Sede espublico | https://utrera.sedelectronica.es/ | Wicket; **tablón `/board` deshabilitado** (oct 2026) |
| Sede legacy | https://sede.utrera.org/ | Timeout desde entorno cloud |
| Licytal Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4109500I | JSF (formulario; sin scrape de filas en esta run) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41095 | Consulta planeamiento provincial |

## Expedientes / planeamiento

- No hay listado público de expedientes urbanísticos enlazable (sede sin tablón activo).
- **Proyectos** se obtienen de:
  - Servicios del departamento de Planeamiento (CPT `project`, categorías `urbanismo-vivienda-y-patrimonio` y `area-urbanismo-vivienda-y-patrimonio`).
  - Búsqueda WP (`pgou`, `plan parcial`, `información pública`, `planeamiento`, etc.).
  - Noticias (`posts`) con términos urbanísticos.
  - Documentación PGOU (decenas de PDFs en página de aprobación provisional 2015 y PGOU 2002).

## Licencias

- Trámite descrito en https://www.utrera.org/project/servicio-de-licencias-urbanisticas/ (informativo, sin histórico).
- Consulta provincial **LicytalPub** (CIF municipal).
- Tablón de edictos en sede espublico **no operativo** (`/board` → página deshabilitada).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** Oficina SIG municipal (solo contacto catastro@utrera.org, sin WMS/WFS público); ide.SEVILLA / geoSEVILLA es de la capital, no Utrera; SITUA sin geometría por expediente municipal.
- **Estrategia:** centroide municipal + jitter en orquestador (`centroid` en manifest).
- **Limitaciones:** PGOU solo PDF; sin visor ArcGIS municipal; sede sin consulta pública de expedientes.

## Limitaciones técnicas

- `sedeutrera.dipusevilla.es` y `sede.utrera.org` inaccesibles (timeout) desde cloud.
- Licytal requiere interacción JSF para listar concesiones.
- SSL en sede espublico: `insecure_ssl: true` en manifest.
