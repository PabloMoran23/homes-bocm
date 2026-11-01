# Sitges — investigación portal ayuntamiento

## Resumen

| Ámbito | URL | Formato |
|--------|-----|---------|
| Web municipal | https://www.sitges.cat | CMS propio; `/serveis/urbanisme` (noticias/contacto). **curl sin UA completo → 403**; `seu.sitges.cat` y WebFetch OK |
| Seu electrònica | https://seu.sitges.cat | Plataforma AOC (Grails): urbanisme, tauler, registre |
| Registre urbanisme | `/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=…` | HTML listados `dElementPublicacioDefecte` + enlace `/registrePublic/registrePublicacio/{id}` |
| Últimas publicaciones | `/registrePublic/ultims` | Paginación `offset`/`max` (~411 páginas históricas) |
| Tauler d'anuncis | `/taulerAnuncisPublic/listPublicacions` | Categoría Urbanisme (`cat.id=10`); búsqueda por texto |
| Transparencia planeamiento | https://seu-e.cat/web/sitges/.../planejament-urbanistic | Enlaces externos RPUC/MUC (no scrape local) |
| CIDO Diputació | https://cido.diba.cat/estatuts/6594916/planejament-urbanistic-ajuntament-de-sitges | Índice normativa (referencia) |

**Código INE:** 08270 (Garraf, Barcelona).

## Proyectos / expedientes

- Cada fila incluye título (`div.titol`), fecha (`data-registre-publicacions` o `dataRegistre`), número de expediente (`2253-000002-001097/2025`), PDFs en `/documentPublic/download/{id}`.
- Categorías relevantes en sidebar urbanisme (IDs observados): **235** (aprobaciones recientes), **236**, **234**, **233**, **20**, **24**, etc.
- El adapter recorre `ultims` + categorías configuradas + tauler (`text=urban`) con límite de páginas.

## Licencias de obra

- No hay listado masivo de licencias de obra mayor en tablón (predominan edictos de planeamiento y licencias de dominio público/eventos).
- **Estrategia:** trámites informativos (web urbanisme + seu) + anuncios del tauler que coinciden con `llicència` / obra / comunicación previa (excluyendo ocupación vía pública/eventos cuando es posible).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor MUC Generalitat: `https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08270`
  - RPUC cerca per municipi: `https://dtes.gencat.cat/rpucportal/...&municipiSel=08270`
  - En transparencia el ayuntamiento remite a RPUC/MUC (sin visor propio ArcGIS/WFS en la seu).
- **Estrategia:** metadatos de expediente en registre; polígonos solo vía MUC/RPUC manual — **sin API estable enlazada al código de expediente del HTML** en el adapter.
- **Limitaciones:** registre = PDF/HTML sin geometría embebida; MUC no expone query automatizable por número de expediente desde la seu.

## Limitaciones técnicas

- `www.sitges.cat` bloquea algunos user-agents (403); usar UA identificable `poc-bocm-sitges/1.0`.
- Histórico del registre muy grande → paginación acotada en manifest (`max_pages`).
- Sin boletín autonómico asociado en cola BOCM (`bocm_count: 0`).
