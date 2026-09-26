# Albaida — investigación portal ayuntamiento

**Municipio:** Albaida (Valencia, Comunitat Valenciana)  
**Slug:** `albaida`  
**INE:** 46024  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.albaida.es | Drupal 10 (Digital Value / portalesmunicipales) — **lento SSL desde CI** |
| Urbanismo — información | https://www.albaida.es/es/content/informacion | Formularios y modelos DR/licencias |
| PGOU | https://www.albaida.es/es/content/plan-general-ordenacion-urbana | Planos, memorias, modificación puntual n.º 5 |
| Polígono industrial Ferrocarril | https://www.albaida.es/es/pagina/poligon-industrial-ferrocarril | Documentación sector industrial |
| Sede electrónica (Dival) | https://albaida.sede.dival.es | **Operativa** — Sedipualba ASP.NET |
| Tablón de anuncios | https://albaida.sede.dival.es/tablondeanuncios/ | **Operativa** |
| Tablón RSS | https://albaida.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista |
| Catálogo urbanismo | https://albaida.sede.dival.es/catalogoservicios.aspx?area=1796&ambito=1 | Trámites URB.001–URB.010 |
| Sede espublico | https://albaida.sedelectronica.es | **Inactiva** — «Seu Electrònica temporalment inactiva» |

## Tablón de anuncios (Sedipualba / Dival)

- **CMS:** ASP.NET Sedipualba (`albaida.sede.dival.es`).
- **Listado:** RSS `tablon_rss.aspx` con título, enlace `anuncio.aspx?id=` y fecha.
- **Documentos:** PDF en `tablondeanuncios/documento.aspx?id=…`.
- **Ejemplos urbanísticos (ago 2026):**
  - Participación ciudadana — estudio integración paisajística (reciclajes La Vall d'Albaida)
  - Edictos presupuestarios / personal (filtrados como no-urbanismo)

## Licencias de obra

- No hay dataset público de concesiones de licencia con coordenadas.
- Catálogo sede con 10 trámites de urbanismo (URB.001 licencias de obras, URB.002–003 DR obras/ocupación, URB.004–010 actividad/ambiental).
- Modelos DR descargables en sede (`carpetaciudadana/documentoplantillaficheroapresentar.aspx`).
- Licencias publicadas aparecen como edictos en tablón cuando el ayuntamiento las anuncia.

## Planeamiento / expedientes

- **Web:** PGOU con planos PDF (clasificación suelo, alturas, unidades ejecución, redes, etc.) y textos (memorias, normas).
- **Modificación puntual n.º 5 PGOU** — aprobación definitiva BOP 74/2017.
- **ICV GVA:** 9 sectores SUZ en InventarioSuSuz (S-1a, S-1b, S-2a, S-2b, S-3, S-4, S-5, S-6, S-7) + zonificación PGOU (exp. 20041308).
- Sin visor municipal de expedientes urbanísticos enlazado a geometría por código.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `terramapas.icv.gva.es/0702_Planeamiento`:
    - Capa `ms:InventarioSuSuz` — 9 polígonos SUZ (cod_ine_mun=46024), fechas aprobación 2009–2012.
    - Capa `ms:Planeamiento.Zonificacion` — ~55 polígonos «Plan general» (exp. 20041308).
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - Sin visor ArcGIS municipal ni WFS local del ayuntamiento.
- **Estrategia:** paginación WFS `STARTINDEX` (filtro CQL del servidor no efectivo); merge polígonos PGOU; matching sector por token (S-1a, S-3, etc.) en títulos del tablón.
- **Limitaciones:**
  - Web municipal con timeouts SSL frecuentes en CI.
  - Geometría por expediente del tablón no disponible; solo sectores ICV y zonificación PGOU.
  - `albaida.sedelectronica.es` inactiva (usar `albaida.sede.dival.es`).

## Limitaciones generales

- Sede histórica espublico inactiva; operativa la sede Dival.
- Tablón RSS con pocos anuncios urbanísticos recientes.
- PDFs PGOU en web con descarga lenta/intermitente.

## Adapter implementado

- `municipio.adapters.albaida:AlbaidaAyuntamientoAdapter`
- Fuentes: tablón RSS Dival + trámites urbanismo + seeds PGOU web + ICV WFS InventarioSuSuz/Zonificacion.
- IDs: `albaida-lic-*` / `albaida-proy-*` (sha256[:14]).
