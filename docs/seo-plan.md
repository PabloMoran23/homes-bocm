# Plan SEO · Homes Urbanismo Madrid

Documento vivo. Dominio: **https://homes-urbanismo.es**

Última revisión: **2026-05-30**

---

## Resumen ejecutivo

Homes concentra licencias urbanísticas, proyectos SIGMA y anuncios BOCM de Madrid capital. El activo SEO principal son las **~3.900 fichas de proyecto** (`/proyecto/[slug]`) y, en segundo lugar, las páginas estáticas (home, estadísticas) y futuras landings por distrito.

**Estrategia:** cola larga primero (expedientes, calles, distritos) → keywords head de urbanismo local → contenido editorial y autoridad.

---

## Estado actual (baseline técnico)

| Elemento | Estado | Notas |
| --- | --- | --- |
| `lang="es"` | ✅ | `app/layout.tsx` |
| Metadata global (title, description, OG) | ✅ | `app/opengraph-image.tsx` 1200×630 |
| `robots.ts` | ✅ | Bloquea rutas dev-only en edición pública |
| `sitemap.xml` | ✅ | ~3.909 URLs (4 estáticas + ~3.905 proyectos) |
| `NEXT_PUBLIC_SITE_URL` | ✅ | `https://homes-urbanismo.es` en Vercel |
| Metadata dinámica en fichas | ✅ | `/proyecto/[id]`, `/ubicacion/[ndp]` |
| Canonical explícito | ✅ | `lib/seo.ts` → layout, estáticas y fichas |
| Analítica (Plausible / GA4) | ⚙️ | Código listo; falta env en Vercel (ver abajo) |
| JSON-LD / datos estructurados | ❌ | Pendiente Fase 1 |
| Google Search Console | ✅ | Propiedad **Dominio**, verificada por DNS TXT |
| Sitemap enviado a GSC | ✅ | |
| Redirect `www` → raíz | ✅ | `middleware.ts` (301 si `NEXT_PUBLIC_SITE_URL` definida) |
| Bing Webmaster Tools | ❌ | Manual — importar desde GSC |

### Slugs de proyecto — decisión tomada

Formato actual: `/proyecto/135-2021-00618` (número de expediente SIGMA).

- **No cambiar por ahora.** Google indexa por `<title>` y contenido, no por el slug.
- El sitemap solo lista URLs; no lleva nombres legibles.
- Slugs legibles (híbridos) valorar en el futuro si hace falta mejorar CTR: `/proyecto/plan-especial-goya-135-2021-00618` + redirects 301.

### Ubicaciones — decisión tomada

~59.500 URLs en `/ubicacion/[ndp]`. **No indexar masivamente aún.** Riesgo de thin content. Incluir en sitemap solo con criterio selectivo (Fase 1).

---

## Audiencias e intención de búsqueda

| Audiencia | Intención | Página objetivo |
| --- | --- | --- |
| Vecinos / compradores | Qué se construye en mi barrio | `/boletin`, `/ubicacion`, landings distrito |
| Profesionales (promotores, arquitectos, inmobiliarias) | Licencias, planeamiento, stats | `/madrid/estadisticas`, `/proyecto`, `/explore` |
| Periodistas / investigadores | Proyecto concreto, BOCM | Fichas `/proyecto/[id]` |
| Long-tail | "Plan especial calle X Madrid", "licencias Chamberí" | Fichas + landings temáticas |

---

## Mapa de keywords

### Alta prioridad

- licencias urbanísticas madrid
- proyectos urbanísticos madrid
- mapa urbanismo madrid
- boletín oficial comunidad madrid urbanismo / BOCM urbanismo
- estadísticas licencias obra madrid
- plan especial madrid [calle/barrio]
- licencias obra [distrito] madrid

### Media (long-tail en fichas)

- expediente SIGMA [número]
- licencia declaración responsable [dirección]
- local convertido vivienda madrid
- reparcelación / estudio detalle [zona]

### Baja (no competir de momento)

- "Homes" (marca genérica)
- Intención compraventa genérica ("comprar piso madrid")

**Naming en SERP:** priorizar "Urbanismo Madrid" / "Homes Urbanismo" en titles y H1, no solo "Homes".

---

## Fases y checklist

### Fase 0 — Fundamentos

- [x] Google Search Console — propiedad **Dominio** `homes-urbanismo.es`
- [x] Verificación DNS TXT en Hostinger
- [x] Enviar `sitemap.xml` a Search Console
- [x] Redirect `www` → raíz (`web/middleware.ts`, 301)
- [x] Imagen OG por defecto (`web/app/opengraph-image.tsx`, 1200×630)
- [x] `alternates.canonical` en layout y rutas principales (`web/lib/seo.ts`)
- [x] Titles SEO en páginas estáticas (`/explore`, `/boletin`, `/madrid/estadisticas`)
- [x] Eventos analítica en código (`boletin_buscar`, `ficha_proyecto_ver`, `estadisticas_filtro`)
- [ ] **Activar analítica en producción** — añadir en Vercel → Environment Variables:
  - `NEXT_PUBLIC_PLAUSIBLE_DOMAIN=homes-urbanismo.es` (Plausible), **o**
  - `NEXT_PUBLIC_GA_MEASUREMENT_ID=G-…` (GA4)
- [ ] Inspeccionar URLs iniciales en GSC: `/`, `/madrid/estadisticas`, `/explore`, 2–3 fichas `/proyecto/...`
- [ ] Bing Webmaster Tools — [bing.com/webmasters](https://www.bing.com/webmasters) → importar desde GSC
- [ ] Auditoría PageSpeed post-deploy — [PageSpeed Insights](https://pagespeed.web.dev/?url=https://homes-urbanismo.es) (home, estadísticas, 1 ficha)

**Eventos analítica (implementados)**

| Evento | Dónde | Props |
| --- | --- | --- |
| `boletin_buscar` | `BoletinAreaApp` | `modo`, `radius_m`, `months` |
| `ficha_proyecto_ver` | `ProyectoViewTracker` | `id`, `kind` (`sigma` \| `bocm`) |
| `estadisticas_filtro` | `MadridDashboard`, `SigmaDashboardTab` | `tab`, `activos` |

---

### Fase 1 — Quick wins técnicos

- [x] Expandir sitemap con fichas SIGMA (`listSigmaFichaSlugs()` → ~3.905 URLs)
- [ ] Datos estructurados JSON-LD:
  - [ ] `WebSite` + `SearchAction` (home)
  - [ ] `Organization` (layout)
  - [ ] `Dataset` (`/madrid/estadisticas`)
  - [ ] `BreadcrumbList` (fichas)
  - [ ] `Place` / coordenadas (ubicaciones, cuando se indexen)
- [ ] Mejorar titles/descriptions de páginas estáticas (orientados a keyword)

| Ruta | Title | Estado |
| --- | --- | --- |
| `/` | (layout default) | ✅ |
| `/explore` | Mapa de urbanismo Madrid: licencias, SIGMA y BOCM | ✅ Fase 0 |
| `/boletin` | Qué ocurre en tu zona — licencias y proyectos… | ✅ Fase 0 |
| `/madrid/estadisticas` | Estadísticas de licencias urbanísticas en Madrid… | ✅ Fase 0 |

- [ ] Texto SEO estático en `/explore` y `/boletin` (H1 + párrafos + FAQ breve encima/debajo del mapa)
- [ ] Párrafo intro server-side en fichas `/proyecto` (contenido indexable además del `<title>`)
- [ ] Breadcrumbs visibles en fichas
- [ ] OG image dinámica o por tipo en fichas proyecto
- [ ] Sitemap index (solo si superamos 50.000 URLs o queremos separar estáticas/proyectos/ubicaciones)

**Indexación selectiva de ubicaciones** (cuando toque)

Criterio propuesto (ajustar):

- Incluir en sitemap si: tiene ≥1 expediente SIGMA activo **y** resumen único en ficha, **o** ≥N licencias recientes.
- Resto: descubrible vía mapa, `noindex` o fuera del sitemap.

---

### Fase 2 — Landings programáticas (mes 2–3)

Páginas con contenido agregado desde JSON + texto editorial (300–600 palabras).

- [ ] **Por distrito** (21 páginas): `/madrid/distrito/chamberi`
  - KPIs filtrados, mapa estático, top proyectos recientes, enlace a explore con filtro
- [ ] **Por tipo de actuación**: `/madrid/licencias/local-a-vivienda`, `/madrid/proyectos/plan-especial`
- [ ] **Por año**: `/madrid/licencias/2024`
- [ ] **Noticias / destacados**: `/proyectos-destacados` (reutilizar `LandingNewsSection`)

Cada landing: entrada en sitemap, `priority` 0.7–0.8, enlaces cruzados entre landings.

---

### Fase 3 — Contenido editorial (mes 3–6)

Guías en `/guia/[slug]` (800–1.500 palabras):

- [ ] Cómo consultar proyectos urbanísticos en Madrid (SIGMA, BOCM, licencias)
- [ ] Qué significa una licencia de obra en Madrid: tipos y plazos
- [ ] Cómo saber si van a construir cerca de tu casa
- [ ] Locales convertidos en vivienda en Madrid: mapa y tendencias
- [ ] Distritos con más licencias en Madrid [año]

Distribución: LinkedIn, prensa urbanística, grupos de vecinos.

---

### Fase 4 — Autoridad y enlaces (continuo)

- [ ] Enlaces internos: footer con distritos, guías, estadísticas
- [ ] Desde fichas: "Ver más en [distrito]", enlace a estadísticas del distrito
- [ ] Link building: medios arquitectura/urbanismo, colegios profesionales, open data
- [ ] Informes trimestrales descargables ("Licencias Madrid Q1 2026") como gancho PR

---

### Fase 5 — Medición y optimización (mensual)

**KPIs**

| Métrica | Objetivo 3 meses | Objetivo 6 meses |
| --- | --- | --- |
| Páginas indexadas (GSC) | 500+ | 3.000+ |
| Impresiones orgánicas/mes | 1.000 | 10.000 |
| Clics orgánicos/mes | 50 | 500 |
| Keywords top 10 | 5 long-tail | 20 long-tail + 2 head |
| CTR medio | >2% | >3% |

**Ritual mensual**

1. GSC → queries, páginas, CTR bajo → mejorar title/description
2. Páginas con impresiones sin clics → reescribir snippet
3. Fichas con tráfico → enriquecer contenido
4. Tras refresh semanal de datos → sitemap se regenera en deploy (no acción manual)

---

## Riesgos y consideraciones

| Riesgo | Mitigación |
| --- | --- |
| 60k ubicaciones = thin content | Indexación selectiva; no incluir todas en sitemap |
| Mapas pesados (LCP en `/explore`) | Landings estáticas rápidas; lazy load mapas |
| Datos públicos — responsabilidad | Footer/aviso legal: fuentes, fecha actualización, disclaimer |
| Cambiar slugs tras indexación | Evitar; si se hace, 301 masivos desde slugs numéricos |
| Marca "Homes" genérica | Reforzar "Urbanismo Madrid" en titles y H1 |

---

## Implementación técnica (referencia código)

| Pieza | Ubicación |
| --- | --- |
| Sitemap | `web/app/sitemap.ts` |
| Robots | `web/app/robots.ts` |
| URL base | `web/lib/site-url.ts` |
| Canonical / OG helpers | `web/lib/seo.ts` |
| OG image | `web/app/opengraph-image.tsx` |
| Analítica | `web/components/Analytics.tsx`, `web/lib/analytics.ts` |
| Redirect www | `web/middleware.ts` |
| Slugs proyecto | `web/lib/sigma-ficha-path.ts` |
| Lista slugs sitemap | `web/lib/load-sigma-ficha.ts` → `listSigmaFichaSlugs()` |
| Metadata fichas | `web/app/proyecto/[id]/page.tsx` |
| Metadata global | `web/app/layout.tsx` |

**Sitemap actual (2026-05-30)**

- 4 estáticas: `/`, `/explore`, `/boletin`, `/madrid/estadisticas`
- ~3.905 proyectos: `/proyecto/{expediente-slug}`
- Total: **3.909 URLs**
- Regeneración: en cada build de producción (`NEXT_PUBLIC_EDITION=public`)

---

## Roadmap visual

```
Fase 0  Fundamentos     █████████░  código ✅ · GSC/Bing manual · activar Plausible/GA4
Fase 1  Técnico         ███░░░░░░░  sitemap ✅ · titles estáticos ✅ · JSON-LD pendiente
Fase 2  Landings        ░░░░░░░░░░  distritos · tipos · años
Fase 3  Editorial       ░░░░░░░░░░  guías
Fase 4  Autoridad       ░░░░░░░░░░  PR · enlaces
Fase 5  Medición        ░░░░░░░░░░  ritual mensual GSC
```

---

## Historial de cambios

| Fecha | Cambio |
| --- | --- |
| 2026-05-30 | **Fase 0 (código):** OG image, canonical, redirect www, analítica + eventos, titles estáticos. |
| 2026-05-30 | Documento inicial. GSC dominio verificado, sitemap ampliado (~3.909 URLs). Slugs numéricos sin cambio. |

---

## Notas / ideas pendientes de priorizar

<!-- Añadir aquí ideas sueltas antes de asignarlas a una fase -->

- Slugs híbridos legibles + ID (futuro, baja prioridad)
- `hreflang` — solo si hay versión en otro idioma
- FAQ schema en home o guías
