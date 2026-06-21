# Villaviciosa de Odón — investigación portal ayuntamiento

## Portal base

- **URL:** https://www.aytovillaviciosadeodon.es
- **CMS:** Liferay (tema `ayto-villaviciosa-odon-theme`)
- **Sede electrónica:** https://sede.aytovillaviciosadeodon.es (STA / tablón virtual — ver limitaciones)

## Verificación anti-bot

Todas las peticiones al portal principal requieren cookie `browser_verified=1` (página intermedia JS «Verificando navegador…»). Sin ella devuelve HTML de verificación, no contenido.

## Fuentes de planeamiento / expedientes

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Anuncios Oficiales | `/actualidad-municipal/anuncios-oficiales` | Liferay asset publisher (acordeón) | Edictos, exposición pública, estudios de detalle, aprobaciones PGOU/planes |
| PGOU | `/es_ES/sede-electronica/plan-general-de-ordenacion-urbana` | HTML + PDFs `/documents/…` | Capítulos y plano PGOU |
| Planeamiento en tramitación | `/tu-ayuntamiento/.../planeamiento-en-tramitacion` | Páginas estáticas Liferay | Plan parcial Vereda-La Portada, plan especial cementerio, estudio detalle UZI 3 |
| Normativa urbanística | `/tu-ayuntamiento/.../plan-general-de-ordenacion-urbana` | HTML + PDFs | Documentación PGOU complementaria |
| Entidades urbanísticas | `/actualidad-municipal/entidades-urbanisticas` | HTML + PDFs | Disolución El Bosque, etc. |

Estructura acordeón en anuncios:

```html
<div class="title-wrapper"><div class="title">TÍTULO</div></div>
...
<a class="document document-pdf target" href="/documents/22602/.../archivo.pdf/...">
```

## Fuentes de licencias

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Licencias de obras | `/tu-ayuntamiento/.../licencias-de-obras` | HTML informativo | Tipos de trámite (LX-VA, LO-ON, etc.) — no concesiones publicadas |
| Anuncios Oficiales | (mismo) | Acordeón | Sin edictos de licencia individuales en el listado actual |
| Tablón sede | `sede.aytovillaviciosadeodon.es/portal/tablonVirtual.do` | STA tablón virtual | **Inaccesible** desde scraper (connection reset) |

No hay listado público de concesiones de licencia con fecha/distrito/coordenadas. Paridad licencias: páginas informativas de trámites + búsqueda en anuncios.

## Limitaciones

1. **Sede electrónica / tablón virtual:** conexión TLS reseteada desde el entorno de scraping; no se integra en esta iteración.
2. **Sin API ni datos abiertos** de expedientes urbanísticos estructurados.
3. **Licencias:** solo trámites informativos; no hay tablón de concesiones scrapeable.
4. **Fechas:** muchos anuncios no incluyen fecha en el HTML; se infiere del nombre del PDF o año en título cuando es posible.
5. **Coordenadas:** no publicadas en ninguna fuente consultada.

## Estrategia adapter

- Cookie `browser_verified=1` en todas las peticiones al portal Liferay.
- Parseo determinista de acordeones en Anuncios Oficiales + crawl páginas urbanismo del mapa web.
- PGOU: un registro por capítulo PDF.
- Licencias: páginas de trámites urbanísticos (como Pozuelo).
