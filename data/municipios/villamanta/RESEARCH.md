# Investigación portal — Villamanta

Municipio: **Villamanta** (`villamanta`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 2 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.villamanta.es | WordPress rt-theme-20 + WPBakery |
| Tablón de anuncios | https://www.villamanta.es/tu-ayuntamiento/tablon-de-anuncios/ | Tarjetas `vc_col-sm-4` con PDF (8 anuncios activos) |
| NNSS | https://www.villamanta.es/tu-ayuntamiento/normativa-municipal/normas-subsidiarias-urbanismo/ | 11 capítulos + planos + SAU 5 + catálogo (~30 PDF) |
| Ordenanzas | https://www.villamanta.es/tu-ayuntamiento/normativa-municipal/ordenanzas/ | Tasas licencias urbanísticas, ordenanzas fiscales |
| Solicitudes / modelos | https://www.villamanta.es/ciudadanos/solicitudes-y-modelos/ | Toggle «Urbanismo» con impresos licencia/DR |
| Sede electrónica | https://sede.villamanta.es | Maggioli eAdmin (PortalCiudadano) |
| Tributos | https://tributosvillamanta.eadministracion.es/ | Impuestos (no urbanismo) |
| Visor QUERCUS | http://81.46.222.82:8080/quercus/sig-alberche/index-28174.php | SIG municipal Alberche (INE 28174) |
| Visor SITCM CM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Planeamiento regional |

## Cómo se listan expedientes / proyectos

1. **Tablón web** — Tarjetas WPBakery con título en `<strong>` y botón PDF (`vc_btn3`). Incluye anuncios de impacto ambiental (fotovoltaica), utilidad pública y presupuestos (filtrados).
2. **NNSS** — Listado estático de capítulos, memorias, planos de ordenación y SAU 5 en PDF.
3. **Noticias WP** — Sin categoría urbanismo dedicada; pocas noticias de planeamiento.
4. **Sede tablón** — `PortalCiudadano/Tablon/wfrTablon.aspx` devuelve error de sesión sin warm-up ASP.NET; no usable de forma fiable.

No hay visor de expedientes urbanísticos ni API JSON de expedientes en curso.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (fecha, tipo, ubicación).
- Formularios descargables en «Solicitudes y modelos» → toggle Urbanismo: licencia urbanística, DR, primera ocupación, segregación, ocupación vía pública.
- Tasas de licencias en ordenanzas (PDF informativos).
- Sede electrónica para presentación telemática; sin listado de concesiones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VILLAMANTA'` (ámbitos NNSS si el servicio responde)
  - Visor QUERCUS Alberche: `index-28174.php` (HTTP, sin API documentada)
  - Visor SITCM Comunidad de Madrid
- **Estrategia:** ingestar ámbitos SITCM como proyectos con `geom_geojson`; enriquecer filas NNSS/tablón si el título menciona código SAU/UE.
- **Limitaciones:** WFS IDEM intermitente (error de conexión backend); QUERCUS sin WFS público; tablón sin coords; licencias sin georreferencia; sede tablón inaccesible.

## Limitaciones generales

- Sede eAdmin requiere sesión ASP.NET; tablón no scrapeable.
- Tablón mezcla anuncios urbanísticos (renovables) con presupuestos y personal (filtrados).
- Sin paginación en tablón; anuncios antiguos en secciones `<h2>`.
- QUERCUS en HTTP (no HTTPS).

## Referencia adapter

Patrón: `venturada.py` / `valdemorillo.py` (WP + SITCM WFS partial + formularios licencia).
