# Coslada — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `coslada` |
| Web oficial | https://coslada.es |
| Sede electrónica | https://sede.ayto-coslada.es |
| CMS | WordPress (Yoast SEO, Zn framework) + subsite `/politica-territorial/` |
| BOCM en pipeline | 24 entradas |

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://coslada.es |
| Política territorial / urbanismo | https://coslada.es/politica-territorial/urbanismo/ |
| Planeamiento (PERI, estudios detalle, reparcelación) | https://coslada.es/politica-territorial/urbanismo/planes-y-proyectos/planes-planeamiento/ |
| PGOU y modificaciones | https://coslada.es/politica-territorial/urbanismo/planes-y-proyectos/planes-pgou/ |
| Convenios urbanísticos | https://coslada.es/politica-territorial/urbanismo/convenios-urbanisticos/ |
| Trámites obra (informativo) | https://coslada.es/politica-territorial/urbanismo/impresos-administrativos/tramites-obra/ |
| Trámites actividad | https://coslada.es/politica-territorial/urbanismo/impresos-administrativos/tramites-actividad/ |
| Transparencia urbanismo | https://coslada.es/transparencia/urbanismo-y-obras-publicas/ |
| Sede / registro | https://sede.ayto-coslada.es |

**Nota entorno agente:** `coslada.es` y `sede.ayto-coslada.es` no resuelven desde el sandbox (timeout/SSL). El espejo accesible `https://cosladapre.toools.es` replica la misma estructura WordPress; el adapter usa `fetch_base` para scrape y normaliza URLs a `coslada.es`.

## Cómo se listan expedientes / proyectos

- **Formato:** HTML WordPress con rejillas `document-icon-row` / `document-icon` (plugin gestor documental).
- Cada fila agrupa PDFs de un mismo expediente (ficha, certificados, BOCM, tablón).
- Títulos en `<span class="title">` junto a miniatura; enlaces directos a `/wp-content/uploads/sites/6/.../*.pdf`.
- **PGOU:** listado plano de memorias, planos, certificados y estudios ambientales por modificación (Barrio del Jarama, etc.).
- **Convenios:** PDFs de aprobación inicial/definitiva y convenio firmado (Avda. España 20, Garaeta, Américas 8, …).
- No hay API JSON ni Drupal views; scrape determinista por HTML + regex.

## Cómo se publican licencias

- **Sede electrónica** (`sede.ayto-coslada.es`): trámites de licencia de obra mayor/menor, actividad, DR — **sin tablón público accesible** en el entorno de scraping.
- **Web informativa:** páginas de trámites en impresos administrativos (obra, actividad, vía pública) con formularios PDF descargables.
- **No** hay dataset abierto de concesiones ni listado tipo STA/Getafe.
- Estrategia adapter: páginas informativas de trámites (patrón Pozuelo) + `min_rows: 0` en validación de licencias.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Enlace desde urbanismo a visor regional **SITCM** (Comunidad de Madrid): https://idem.madrid.org/cartografia/sitcm/html/visor.htm — mapa PGOU regional, sin query por código de expediente municipal ni WFS por proyecto.
  - PDFs de planeamiento (planos, fichas) sin GeoJSON embebido ni servicio ArcGIS municipal detectado.
  - Sede y tablón no accesibles para comprobar visor embebido.
- **Estrategia:** no implementar `_fetch_geometry`; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** solo documentación PDF; visor regional no enlazable a expediente; producción `coslada.es` bloqueada en red del agente (espejo toools para desarrollo).

## Limitaciones

- Dominio producción y sede inaccesibles desde CI/agente (timeout).
- Sin listado público de licencias concedidas.
- Sin geometría por expediente.
- Paginación en blog urbanismo (noticias de obras) — excluido del adapter (no son expedientes).
- Espejo `cosladapre.toools.es` marcado `noindex` (staging); URLs canónicas en salida apuntan a `coslada.es`.

## Adapter implementado

- `municipio/adapters/coslada.py` — `CosladaAyuntamientoAdapter`
- Fuentes: rejillas PDF planeamiento + PGOU + convenios; licencias informativas.
