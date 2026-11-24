# Ibi — investigación portal ayuntamiento

**Municipio:** Ibi (Alicante, Comunitat Valenciana)  
**INE:** `03077`  
**BOCM:** sin boletín asociado en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Rol | URL |
|-----|-----|
| Web corporativa | https://www.ibi.es |
| Urbanismo | https://www.ibi.es/ciudadania/urbanismo/ |
| PGOU | https://www.ibi.es/ciudadania/p-g-o-u-plan-general-ordenacion-urbana/ |
| Planes parciales | https://www.ibi.es/ciudadania/planes-parciales-pps/ |
| Reforma interior (PRI) | https://www.ibi.es/ciudadania/planes-de-reforma-interior-pris/ |
| Sede electrónica | https://ibi.sedipualba.es |
| Tablón anuncios | https://ibi.sedipualba.es/tablondeanuncios/ |
| Tablón RSS | https://ibi.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo Urbanismo (área 1522) | https://ibi.sedipualba.es/catalogoservicios.aspx?area=1522&ambito=1 |

## Tecnología

- **ibi.es:** WordPress + Elementor + WPML (paths `/ciudadania/…`).
- **ibi.sedipualba.es:** ASP.NET Sedipualba (Diputación de Albacete). Tablón, catálogo de trámites (códigos `GU*` / `TE*`), CSV en PDFs.
- **ibi.sede.dival.es:** no responde; la sede activa es **sedipualba**, no Dival.

## Proyectos / expedientes urbanísticos

1. **ICV InventarioSuSuz** — sectores SU/SUZ y unidades de ejecución con polígono WFS (`cod_ine_mun=03077`).
2. **Web ibi.es** — secciones PGOU, PP, PRI (contenido editorial; pocos PDF directos en HTML).
3. **Tablón sedipualba** — edictos varios; RSS reciente dominado por subvenciones/AAVV; filtro por palabras clave urbanísticas.

No hay visor municipal propio ni API JSON de expedientes urbanísticos.

### Cómo se listan

- **WordPress:** páginas estáticas por tipo de instrumento.
- **Tablón:** RSS 2.0 (ISO-8859-1) + `anuncio.aspx?id=…`.
- **ICV:** WFS GML3 con `CQL_FILTER cod_ine_mun='03077'`.

## Licencias de obra

- No hay registro público de licencias concedidas (listado con fecha/dirección).
- **Catálogo sede:** GU01 (DR obra), GU11 (solicitud licencia obra), GU09 (1ª ocupación), GU07 (inicio obra), etc.
- **Tablón:** edictos puntuales si se publican; mayoría de anuncios no urbanísticos en ventana RSS.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
  - Polígonos de sectores/unidades aprobados en planeamiento (no geometría por expediente de licencia).
- **Estrategia:** descarga WFS filtrada por INE (`cod_ine_mun=03077`) + descarte en adapter si el centroide cae fuera del bbox municipal (ICV mezcla erróneamente sectores lejanos con el mismo código).
- **Limitaciones:** licencias solo en PDF/edicto sin georreferencia; polígonos ICV para Ibi poco fiables (2 sectores PP-X con coordenadas fuera del término en nov 2026).

## Limitaciones generales

- Sin listado machine-readable de expedientes en curso.
- Tablón RSS con mucho ruido administrativo.
- Trámites sede son fichas informativas, no concesiones publicadas.
