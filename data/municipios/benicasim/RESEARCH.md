# Benicasim — investigación portal ayuntamiento

Municipio: **Benicasim** (Benicàssim, `benicasim`) — Castellón, Comunitat Valenciana  
Boletín: DOGV (`dogv`, 1 entrada BOCM)  
INE municipio: `12018`

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa (WordPress + WPBakery) | https://ayto.benicassim.es |
| Urbanismo / trámites | https://ayto.benicassim.es/urbanismo/ |
| Planeamiento | https://ayto.benicassim.es/planeamiento/ |
| PGOU (normas, hojas PDF, mapas) | https://ayto.benicassim.es/urbanismo/plan-general-de-ordenacion-urbana/ |
| Mapas PGOU interactivos (HTML) | https://ayto.benicassim.es/dms/ayuntamiento/urbanisme/PGOU/MapaOS/PGOU2000.html |
| Sede electrónica (espublico gestiona) | https://benicassim.sedelectronica.es |
| Tablón de anuncios | https://benicassim.sedelectronica.es/board |
| Catálogo trámites | https://benicassim.sedelectronica.es/dossier.8 |
| Transparencia | https://benicassim.sedelectronica.es/transparency |

## Cómo se listan expedientes / proyectos

1. **PGOU municipal** — página estática WordPress con ~27 PDFs en `/dms/ayuntamiento/urbanisme/PGOU/` (normas, hojas 1:2000 y 1:5000, planes especiales villas) y mapas HTML `MapaOS/PGOU2000.html`, `PGOU5000.html`.
2. **Planeamiento** — página informativa con enlaces a PGOU y PDFs en `wp-content/uploads` (`CRITERIOS-INTERPRETATIVOS-PGOU.pdf`, `MODIFICACIONES-PGOU.pdf`).
3. **Sede espublico** — tablón `/board` en HTML (Wicket); ~10 filas visibles por página. En la muestra actual predominan anuncios administrativos (modificación créditos, empleo público); sin filas urbanísticas activas en el momento de la investigación.
4. **ICV GVA WFS** — capa `InventarioSuSuz` con 8 ámbitos SUZ/SU para `cod_ine_mun=12018` (UE 1–5, SECTORES I1, I2, R1).

## Licencias de obra

- No hay listado histórico público de concesiones de licencias.
- Trámites en sede (`/dossier.8`): licencias de obra, comunicaciones previas, declaraciones responsables (catálogo espublico).
- Página web `/urbanismo/` describe trámites presenciales y telemáticos (certificado digital).
- El adapter devuelve páginas informativas del tablón, catálogo de trámites y urbanismo web (patrón Pozuelo/Alcalà de Xivert).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento?service=WFS&typeName=InventarioSuSuz` — 8 polígonos Benicàssim (`cod_ine_mun=12018`): UE 1–5, SECTOR I1, SECTOR I2, SECTOR R1.
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz
  - Mapas PGOU municipal (HTML estático 1:2000/1:5000) — sin API ni enlace a expediente.
- **Estrategia:** paginar WFS InventarioSuSuz (filtro CQL del servidor no funciona) y filtrar por `cod_ine_mun=12018`; emparejar geometría en tablón/PDF por palabras clave (UE, sector).
- **Limitaciones:** sin visor municipal ArcGIS enlazado a expediente; tablón sede sin coords; geometría solo a nivel sector/UE del inventario autonómico, no por licencia individual. Carga WFS completa ~45 s (paginación ~8.400 features).

## Limitaciones generales

- Tablón sede paginado (~10 filas visibles); sin API JSON.
- WFS ICV ignora `CQL_FILTER` — requiere paginación client-side.
- Sin re-parse BOCM/DOGV; proyectos del boletín ya en `projects.json`.
