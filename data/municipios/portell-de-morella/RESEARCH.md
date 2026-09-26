# Portell de Morella — investigación portal ayuntamiento

**Municipio:** Portell de Morella (Castellón, Comunitat Valenciana)  
**Slug:** `portell-de-morella`  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)  
**INE:** 12091

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.portelldemorella.es | **Operativa** — Drupal 9 (tema Toools, portalesmunicipales L01120918) |
| Sede electrónica | https://portelldemorella.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://portelldemorella.sedelectronica.es/board | **Operativa** — 3 filas (ago 2026), sin urbanismo |
| Portal transparencia | https://portelldemorella.sedelectronica.es/transparency | **Operativa** — carpeta 7. URBANISMO (9 docs), navegación Wicket AJAX |
| Catálogo trámites | https://portelldemorella.sedelectronica.es/dossier | Lento / timeout en CI |
| Consulta expedientes | https://portelldemorella.sedelectronica.es/expedientes | Requiere Cl@ve |
| Portal transparencia (web) | https://www.portelldemorella.es/es/portal-de-transparencia | Redirige a sede |
| Registro planeamiento GVA | https://mediambient.gva.es/es/auto/urbanismo/reg-planeamiento/3%20CASTELL%C3%93N/12091%20PORTELL%20DE%20MORELLA/ | Índice Liferay (sin listado HTML scrapeable) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcalà de Xivert/Cártama.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Contenido actual (ago 2026):** censo electoral y bolsa de empleo; sin licencias ni planeamiento publicados.

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites informativos: catálogo sede `/dossier` y consulta `/expedientes` (autenticación).
- Las licencias concedidas aparecerían en el tablón como edictos cuando se publiquen.

## Proyectos / planeamiento

- **PGOU:** aprobación provisional del Texto Refundido (2013, redactado por AUG-Arquitectos); sin visor ni PDFs indexados en la web corporativa.
- **Transparencia sede:** sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 9 documentos; requiere navegación AJAX Wicket (no URLs UUID estáticas en raíz).
- **Noticias Drupal:** obras públicas urbanas (renovación lavadero, mejoras de aceras, lugares de descanso) publicadas en `/es/noticias/*`.
- **ICV Inventario SU-SUZ:** sin ámbitos registrados para `cod_ine_mun=12091` en WFS regional (consulta ago 2026).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - ICV WFS `InventarioSuSuz` y `Planeamiento.Zonificacion` en `terramapas.icv.gva.es/0702_Planeamiento` — 0 features con `cod_ine_mun=12091`.
  - Visor GVA `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz` — sin capas del municipio.
  - Web Drupal — sin mapa interactivo PGOU ni shapefiles.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [40.5183, -0.2650]`).
- **Limitaciones:**
  - Municipio pequeño (155 hab.) sin visor urbanístico propio.
  - Transparencia urbanismo no scrapeable sin sesión Wicket AJAX completa.
  - PGOU en tramitación histórica sin geometría pública en ICV.

## Limitaciones generales

- Tablón sin entradas de urbanismo recientes.
- `/dossier` inestable (timeout) en entorno CI.
- Sin datos abiertos de licencias ni expedientes listados.

## Adapter implementado

- `municipio.adapters.portell_de_morella:PortellDeMorellaAyuntamientoAdapter`
- Fuentes: noticias Drupal (obras urbanas) + transparencia sede (metadatos) + PGOU conocido + tablón sede + páginas informativas de trámites.
