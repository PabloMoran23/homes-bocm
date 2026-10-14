# Peñíscola — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web corporativa | https://www.peniscola.org | CMS vgcomunicacion (`/ver/{id}/...`) | Urbanismo, PGOU, planes parciales, PATIVEL, reparcelación Cap Blanc |
| Sede electrónica | https://sede.peniscola.org | STA T-Systems / TAO | Trámites y tablón |
| Tablón anuncios | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all` | JSON embebido `dataset_PTS2_TABLON` (~278 filas) | Licencias y edictos urbanísticos |
| Catálogo trámites | `.../doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO` | JSON embebido `dataset_CATSERV` | Trámites informativos (licencias, certificados) |
| Tablón web (enlace) | https://www.peniscola.org/ver/1428/Tabl%C3%B3n-de-anuncios.html | Enlaces a sede STA | Semilla de navegación |

**Nota:** La página `PTS2_TABLON_AYTO` no incluye dataset en HTML; hay que usar `PTS2_TABLON` con `KEY=all` (mismo patrón que Elx/Dénia).

## Semillas urbanismo (web)

- `/ver/868/Urbanismo.html` — índice departamento
- `/ver/924/PGOU-Vigente.html`
- `/ver/932/Plan-Especial-de-Protección-del-Casco-Antiguo.html`
- `/ver/7032/Proyecto-de-Reparcelación-Cap-Blanc.html`
- `/ver/8897/PATIVEL.html`
- `/ver/9355/Estrategias-Ordenación-Peñíscola.html`

## Licencias

- No hay dataset público de concesiones individuales con coordenadas.
- El tablón STA publica edictos y anuncios (~26 entradas con keywords urbanismo/licencia/obra en el scrape de investigación).
- El catálogo STA lista trámites de licencia (páginas informativas).

## Proyectos / expedientes

1. **Web:** páginas estáticas y PDFs enlazados desde sección Urbanismo.
2. **Tablón STA:** `descriptionProc`, `externString`, `pubDateIni`, `dboid`.
3. **ICV:** capas de zonificación con `cod_ine_mun=12079`.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:** ICV WFS `Planeamiento.Zonificacion` en `https://terramapas.icv.gva.es/0702_Planeamiento` (filtro `cod_ine_mun=12079`). Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion`
- **Estrategia:** paginación WFS (`startIndex` 0–14000, `count=500`); cruce por denominación del ámbito / sector en título del proyecto.
- **Limitaciones:** sin visor municipal con enlace expediente→polígono; tablón y web son PDF/HTML sin georreferencia explícita. Licencias sin geometría en portal.

## Limitaciones generales

- Sede STA: respuesta del tablón con `KEY=all` es pesada (~270 KB HTML); requiere timeout ≥90s.
- No hay RSS de tablón en sede (solo STA embebido).
- Cita previa urbanismo: atención presencial (documentado en web).
