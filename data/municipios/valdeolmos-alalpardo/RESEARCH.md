# Valdeolmos-Alalpardo — investigación portal ayuntamiento

**Municipio:** Valdeolmos-Alalpardo (`valdeolmos-alalpardo`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 13)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://www.valdeolmos-alalpardo.org |
| Normativa urbanística | https://www.valdeolmos-alalpardo.org/normativa-urbanistica/ |
| Normas subsidiarias (NNSS) | https://www.valdeolmos-alalpardo.org/normativa-urbanistica/normas-subsidiarias/ |
| Planes especiales | https://www.valdeolmos-alalpardo.org/normativa-urbanistica/planes-especiales/ |
| Transparencia planeamiento | https://www.valdeolmos-alalpardo.org/portal-de-transparencia/planeamiento-urbanistico-ayuntamiento/ |
| Trámites urbanismo | https://www.valdeolmos-alalpardo.org/wp-login-phploggedouttruewp_langes_es/tramites-de-urbanismo/ |
| Sede electrónica (espublico gestiona) | https://valdeolmos-alalpardo.sedelectronica.es |
| Tablón de anuncios | https://valdeolmos-alalpardo.sedelectronica.es/board |
| Cartografía regional (SIT) | http://www.madrid.org/cartografia/planea/index.htm |
| NOMECALLES | http://www.madrid.org/nomecalles/ (municipio 1625) |

## Cómo se listan expedientes / proyectos

1. **Normativa web** — WordPress con PDFs de NNSS (memorias, planos de ordenación, normas urbanísticas) en `valdeolmos-alalpardo.org` y `valdeolmos-alalpardo.eu`. Documentación UE-22 (julio 2026) en página de normativa urbanística.
2. **Planes especiales** — Listado de planes CCAA que afectan al municipio (ZEPA, refuerzo ramal este, etc.).
3. **Ámbitos SITCM** — WFS Comunidad de Madrid con ~30 polígonos UE/SAU/APD del municipio.
4. **Tablón sede** — HTML Wicket en `/board` con `preview-document/{uuid}`. A agosto 2026 predomina tributos/calendario fiscal; entradas urbanísticas esporádicas.
5. **Portal transparencia web** — Planeamiento urbanístico con enlaces a NNSS y planes especiales; sin listado JSON de expedientes.

No hay visor urbanístico propio del ayuntamiento ni API de expedientes públicos.

## Cómo se publican licencias

- **Formularios web** en sección «Trámites de urbanismo»: licencia obra mayor, declaraciones responsables (inicio obra, primera ocupación), segregación/division.
- **Tablón sede** — Concesiones/notificaciones cuando se publican (actualmente sin entradas de licencia visibles).
- **Oficina tributaria** (eadministracion.es) para tasas urbanísticas; no dataset de licencias concedidas.
- No hay dataset abierto de licencias con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='VALDEOLMOS-ALALPARDO'`
  - Campos: `DS_NOMB_AMB` (código ámbito, p. ej. UE-22, SAU-1), `DS_FIG_DES`
- **Estrategia:** Cargar todos los ámbitos del municipio desde WFS; enriquecer por código UE/SAU/APD en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y PDFs normativos no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento, no parcelas de licencias individuales.
  - Cartografía CCAM (`madrid.org/cartografia/planea`) es visor regional sin API expediente enlazable.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); sin API JSON del tablón.
- Planeamiento vigente: NNSS 1997 (BOCM 50/1997); sin PGOU digital propio.
- PDFs históricos en dominio `valdeolmos-alalpardo.eu` además de `.org`.
- Urbanismo atiende con cita previa (miércoles y viernes).

## Referencias de patrón

- Adapter similar: `municipio/adapters/el_molar.py` (WordPress + sede espublico + WFS SIT)
- Geometría WFS: `sector_geometry/madrid_ayto_sync.py`
