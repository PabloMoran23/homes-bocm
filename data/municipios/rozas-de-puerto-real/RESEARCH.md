# Rozas de Puerto Real — investigación portal ayuntamiento

**Slug:** `rozas-de-puerto-real`  
**Comunidad:** Comunidad de Madrid  
**BOCM:** 4 entradas históricas

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal (WordPress LivingStore) | https://rozasdepuertoreal.es | Yoast SEO, plugin LSVR (documentos/eventos) |
| Tablón web | https://rozasdepuertoreal.es/tablon-de-anuncios/ | Noticias municipales (poco urbanismo) |
| Documentos tramites | https://rozasdepuertoreal.es/documents/ | PDFs solicitud licencia, DR urbanística |
| Sede electrónica eAdmin | https://sederozasdepuertoreal.eadministracion.es | Maggioli ATM SPA |
| Tablón sede | https://sederozasdepuertoreal.eadministracion.es/PortalCiudadano/Tablon/wfrTablon.aspx | Grid DevExpress; requiere sesión/cookies |
| Portal transparencia | https://transparenciarozasdepuertoreal.eadministracion.es | **Portal no disponible** |
| Visor SITCM CM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Referencia regional |

## Expedientes / proyectos

- **SITCM WFS:** capa `sitcm:VPLA_V_AMBITO` con 7 unidades de actuación (UA-A … UA-G) derivadas de Normas Subsidiarias 1984 (MATRIZ).
- **WordPress:** post «Proyecto inmobiliario 2024» (plan VPO jóvenes, enlace externo plandeviviendajovenrdpr.wordpress.com).
- **Sede tablón:** anuncios administrativos (pleno, OEP); sin edictos urbanísticos en la muestra actual.
- No hay sección dedicada de planeamiento en la web corporativa ni PGOU digital accesible.

## Licencias de obra

- No hay listado público de licencias concedidas.
- **Documentos web:** formularios PDF de solicitud licencia urbanística, declaración responsable urbanística, licencia apertura, vado.
- **Sede eAdmin:** catálogo de procedimientos no scrapeable (SPA); presentación telemática.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='ROZAS DE PUERTO REAL'`
  - Campo ámbito: `DS_NOMB_AMB` (UA-A … UA-G)
  - Visor web: SITCM Comunidad de Madrid
- **Estrategia:** descarga masiva de ámbitos NNSS vía WFS GetFeature; match por código UA en títulos.
- **Limitaciones:** sin visor urbanístico municipal; portal transparencia inactivo; licencias sin georreferencia; expedientes del tablón sin polígono individual salvo match SITCM.

## Limitaciones generales

- Portal transparencia eAdmin devuelve «PORTAL NO DISPONIBLE».
- Sede tablón requiere warmup de sesión; contenido urbanístico mínimo.
- Sin dataset abierto de licencias concedidas.
- Web corporativa con poca documentación de planeamiento vigente.
