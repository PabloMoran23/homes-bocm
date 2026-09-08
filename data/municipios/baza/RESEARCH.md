# Baza — investigación portal ayuntamiento

**Municipio:** Baza (Granada, Andalucía)  
**Slug:** `baza`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18022

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web municipal | https://ayuntamientodebaza.es | **Operativa** — WordPress Soledad 8.6 + Elementor + WP File Download 4.9 |
| Tablón de anuncios | https://ayuntamientodebaza.es/tramites/tablon-de-anuncios/ | **Operativa** — wpfd categoría 1105 (~100 filas/página, 6 páginas AJAX) |
| Urbanismo | https://ayuntamientodebaza.es/c-i-urbanismo-y-patrimonio/ | Área de gobierno; PDF modificación PGOU (jun 2024) |
| Sede Berger Levrault | https://sede.ayuntamientodebaza.es | Enlace desde web; **timeout en CI** (transformación digital 2022) |
| Sede espublico | https://baza.sedelectronica.es | **No configurada** — página "seleccione su sede" |
| SITUADIFusión | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOU digitalizado regional (Granada → Baza) |
| wpfd sitemap | https://ayuntamientodebaza.es/wp-sitemap-posts-wpfd_file-1.xml | ~1121 entradas wpfd_file (ordenanzas, tablón, planeamiento) |

## Expedientes / proyectos

1. **Tablón wpfd (categoría 1105):** Tabla HTML con enlaces `download/1105/tablon-de-anuncios/{id}/{slug}.pdf` y atributo `title`. Paginación vía AJAX (`admin-ajax.php?action=wpfd`); adapter scrapea página 1 + wpfd sitemap para planeamiento.
2. **wpfd sitemap:** Documentos de planeamiento indexados como páginas `wpfd_file/`:
   - Aprobación inicial delimitación innovación PGOU SUNS-2 sectorización Ctra. Murcia (exp. 7478/2022)
   - Avance innovación PGOU UE-20
   - Plan parcial sector SUS-I-02-35 (Fralomar SL)
   - Normas urbanísticas Baza (jun 2010)
   - Mapas clasificación suelos (urbano, urbanizable sectorizado/no sectorizado)
3. **Sección urbanismo:** PDF `2-modificacion-Baza-Junio-2024.pdf` (modificación PGOU).
4. **SITUADIFusión:** Visor regional embebido; planeamiento escaneado, no listado de expedientes individuales del ayuntamiento.

## Licencias de obra

- **Sin dataset público** de licencias concedidas con coordenadas.
- Trámites vía sede Berger Levrault (licencias y permisos según noticia sede 2022).
- Tablón wpfd puede incluir edictos de licencia/actividad cuando se publiquen (filtrado por regex).
- Adapter devuelve páginas informativas de tablón + urbanismo + sede (patrón Pozuelo/Baeza).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUADIFusión / VITUA (Junta de Andalucía): planeamiento digitalizado raster; sin API REST enlazable por código de expediente municipal.
  - wpfd mapas PGOU (clasificación suelos): PDFs cartográficos sin GeoJSON/WFS.
  - Diputación Granada portal transparencia: sin visor ArcGIS municipal detectado para Baza.
  - Sede Berger Levrault: consulta expedientes con autenticación; sin geometría pública.
- **Estrategia:** No aplicable; orquestador usará centroide municipio (37.4907, -2.7725) + jitter.
- **Limitaciones:** Tablón paginado vía AJAX (solo primera página en scrape directo); PGOU/SUNS en PDF sin georreferencia vectorial.

## Limitaciones técnicas

- `www.baza.es` no resuelve; dominio activo es `ayuntamientodebaza.es`.
- `baza.sedelectronica.es` sin tablón operativo.
- `sede.ayuntamientodebaza.es` inaccesible desde CI (timeout); documentado para sync manual.
- wpfd REST API (`wp/v2/wpfd_file`) no expuesta (404).
- Certificados SSL válidos; `insecure_ssl` no requerido.

## Adapter implementado

- `municipio.adapters.baza:BazaAyuntamientoAdapter`
- Fuentes: tablón wpfd (pág. 1) + wpfd sitemap (planeamiento) + PDF urbanismo + fila SITUA + trámites informativos.
