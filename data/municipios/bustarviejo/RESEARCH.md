# Bustarviejo — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web municipal (WordPress) | https://www.ayuntamientodebustarviejo.org | Dominio efectivo; `bustarviejo.org` no resuelve |
| Sede electrónica eAdmin | https://bustarviejo.eadministracion.es/home | SPA Angular Maggioli/ATM |
| Portal transparencia | https://transparenciabustarviejo.eadministracion.es/portal | PGOU, tablón, visor SIT |
| Tablón de anuncios | https://transparenciabustarviejo.eadministracion.es/transparencia/tablon-de-anuncios | Edictos urbanísticos |
| PGOU 2022 | https://transparenciabustarviejo.eadministracion.es/transparencia/tablon-de-anuncios/urbanismo---pgou-2022 | Documentación planeamiento |
| Carpeta tributaria | https://tributosbustarviejo.eadministracion.es | Tasa servicios urbanísticos (licencias) |
| Visor SIT CM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Enlace desde transparencia |

## Expedientes / proyectos

- **Transparencia eAdmin:** secciones estáticas con PDFs (PGOU 2022, enajenación parcelas Fuente Milano, proyectos de acondicionamiento). HTML server-side cuando el portal responde; en la investigación del cron devolvió HTTP 503 de forma intermitente.
- **SITCM WFS:** capa `sitcm:VPLA_V_AMBITO` con 44 ámbitos del PGOU (P-1…P-40, ENSANCHE, RESERVA URBANA, EL ROBLEDAL, etc.) — fuente principal con geometría.
- **WordPress:** noticias y plenos; escasos anuncios urbanísticos directos (p. ej. precios públicos BOCM).

## Licencias de obra

- No hay listado público de concesiones en sede ni transparencia.
- **Tributos:** autoliquidación «Tasa Servicios Urbanísticos» (licencia de obras, DR, comunicación previa) en carpeta tributaria.
- **Sede eAdmin:** trámites telemáticos tras pago de tasa; sin tablón scrapeable en la SPA.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='BUSTARVIEJO'`
  - Campo ámbito: `DS_NOMB_AMB` (p. ej. `P-1 CASCO ANTIGUO`, `P-23A RESERVA URBANA`)
  - Visor web: SITCM (enlace en portal transparencia)
- **Estrategia:** descarga masiva de ámbitos municipales vía WFS GetFeature; enriquecimiento puntual por código P-N en títulos de anuncios.
- **Limitaciones:** portal transparencia inestable (503); licencias sin georreferencia; WP sin visor propio. Expedientes puntuales del tablón sin polígono individual salvo match por nombre de ámbito SIT.

## Limitaciones generales

- `bustarviejo.org` / `bustarviejo.es` no accesibles desde el entorno del agente.
- Portal transparencia eAdmin con disponibilidad intermitente.
- Sede eAdmin es SPA sin API pública de tablón.
- Sin dataset abierto de licencias concedidas.
