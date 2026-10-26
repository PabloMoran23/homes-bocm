# Torre-Pacheco — investigación portal ayuntamiento

**Municipio:** Torre-Pacheco (Murcia)  
**INE:** 30037

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.torrepacheco.es | WordPress; área Urbanismo (descriptiva). **F5 503** desde IP cloud del agente |
| Sede electrónica STA | https://sede.torrepacheco.es | T-Systems STA: tablón, catálogo trámites, carpeta ciudadana |
| Tablón de anuncios | https://sede.torrepacheco.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | Dataset JS embebido `dataset_PTS2_TABLON` (~45 entradas vigentes) |
| Catálogo trámites | https://sede.torrepacheco.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | `dataset_CATSERV` (~216 procedimientos; licencias/DR/comunicaciones urbanísticas) |
| Transparencia | https://transparencia.torrepacheco.es | WordPress; bloque “Urbanismo y vivienda” enlaza a web corporativa |
| BORM | https://www.borm.es | Anuncios de planeamiento (p. ej. modificación AUR 5, PEOR Roldán) — no scrapeado (boletín regional) |

## Listado de expedientes / proyectos

- **Tablón STA:** JSON en página (`dboid`, `descriptionProc`, `pubDateIni`, `remitent`). Detalle vía `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
- **Transparencia:** sin repositorio documental estructurado de planeamiento en WP-JSON; solo descripción de competencias en `/5991-2/`.
- Expedientes urbanísticos relevantes aparecen como edictos / información pública en el tablón (p. ej. licencia de actividad Av. Juan Carlos I).

## Licencias

- No hay dataset abierto de licencias concedidas con dirección/coordenadas.
- Edictos de licencia / información pública en tablón STA.
- Catálogo STA expone trámites informativos: licencia urbanística, DR obras, comunicación previa, convenio urbanístico, etc.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS CARM planeamiento: `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` con `Municipio='Torre Pacheco'` (~201 polígonos; campo `Ambito`, p. ej. `Aur nº 4. Torre Pacheco.`, `SGEL. Aur nº 2.`).
  - Ficha regional: enlaces `Enlace_ficha` → `opweb.carm.es/sitmurcia/...` (visor SITMURCIA, sin API expediente↔polígono directa).
- **Estrategia:** índice WFS en memoria; match por tokens en título (`AUR nº N`, `Roldán`, palabras del ámbito).
- **Limitaciones:** WFS es clasificación de suelo (no expediente puntual); sede con certificado TLS incompleto; web principal bloqueada en cloud; tablón sin geometría; licencias sin georreferencia.

## Notas técnicas

- `sede.torrepacheco.es`: cadena TLS incompleta → `sede_insecure_ssl: true` en manifest.
- Comunidad autónoma: **murcia** (sin boletín BOCM asociado en cola).
