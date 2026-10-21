# Sabadell — investigación portal ayuntamiento

Municipio: **Sabadell** (`sabadell`) — Barcelona, Catalunya. INE `08187`.

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal | https://web.sabadell.cat | Joomla; urbanismo y cartografía |
| Sede electrónica (OpenSIAC) | https://seu.sabadell.cat/opensiac/ | Trámites, tablón, información pública |
| Carpeta ciudadana / obras | https://seua.sabadell.cat/sedelectronica/p/TramitsCarpeta_esp.asp | Consulta expedientes con certificado/NIF |
| Planejament urbanístic | https://web.sabadell.cat/urbanisme/planejament-urbanistic | PGMOS, modificaciones, enlace geoportal |
| Text refós PGMOS | https://web.sabadell.cat/urbanisme/planejament-urbanistic/text-refos-del-PGMOS | PDFs normativos y anexos sectores |
| Plànol / geoportal (pruebas) | https://planol.sabadell.cat/Planol/inici?code=urban | Visor capas PGMOS, PEPS, figures en trámite |
| Metadades IDE | https://catalegs.ide.cat/geonetwork/srv/api/records/planejament-urbanistic-sabadell | Conjunto «Planejament urbanístic de Sabadell» |
| Trámites urbanismo | https://seu.sabadell.cat/opensiac/action/tramites?method=enter | Agrupación «Urbanisme, habitatge, llicències…» |

## Listado de expedientes / proyectos

- **OpenSIAC — información pública / tablón:** búsqueda POST en `infopublica_search.action` (edictos `OTROS`, `CP`) con filtro «Ajuntament de Sabadell». Filas enlazan a `infopublica_ver.action?id=…` con PDFs adjuntos.
- **PGMOS / planeamiento:** no hay listado HTML de expedientes; documentación estructurada en text refós + geoportal. Modificaciones puntuales (p. ej. MPG-127 usos recreativos/turísticos, DOGC 15/06/2023) enlazadas desde la sección de planejamiento.
- **Carpeta ciudadana:** consulta de licencias de obra por titular (requiere identificación); no es fuente batch pública.

## Licencias de obra

- No hay dataset abierto de concesiones (como tablón CSV). Trámites electrónicos nivel 4 en sede (parcelación id=36, obras, etc.).
- El adapter registra **páginas informativas** de trámites y el tablón OpenSIAC; cuando la sede responde, añade edictos urbanísticos del buscador.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Plànol municipal `planol.sabadell.cat` — visor en pruebas con capas «Text Refós PGMOS 2020», figures de planejament, PEPS (bienes protegidos). Metadato IDE apunta al visor como «Map viewer»; **no** se ha localizado endpoint ArcGIS REST/WFS público documentado.
  - Conjunto vectorial EPSG:25831 descrito en IDE (series N-0…N-3, PEPS); distribución principal PDF/planos en `web.sabadell.cat/planols`.
- **Estrategia:** seeds PGMOS + tablón; intento de detectar URL MapServer en HTML del Plànol (`_try_planol_arcgis_hint`). Sin query REST estable → sin `geom_geojson` en adapter; orquestador usa `centroid` manifest + jitter.
- **Limitaciones:** Dominios `*.sabadell.cat` frecuentemente inaccesibles (timeout SSL) desde el entorno cloud del agente; geometría por expediente no enlazable. Carpeta ciudadana requiere login.

## Limitaciones generales

- Timeout SSL hacia `web.sabadell.cat`, `seu.sabadell.cat`, `planol.sabadell.cat` en CI cloud (adapter sigue funcionando con seeds IDE + URLs estáticas PGMOS).
- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Sync Supabase: depende de `SUPABASE_DB_URL` en el entorno de ejecución.
