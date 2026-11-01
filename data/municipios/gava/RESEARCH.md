# Gavà — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial (Liferay) | https://www.gavaciutat.cat | Urbanisme, planejament aprovat/en exposició, plans parcials/especials, PGM |
| Sede electrónica STA (TAO) | https://eseu.gava.cat | Catálogo `PTS_CATSERV` (~312 trámites); tablón `PTS2_TABLON` (ordenanzas fiscales) |
| Seu-e (datos abiertos) | https://www.seu-e.cat/ca/web/gava/dades-obertes | Portal transparencia CCAA (sin dataset urbanístico enlazado al adapter) |
| Agenda urbana | https://agendaurbana.gava.cat | Visor/agenda (timeout o bloqueo desde entorno automatizado) |
| AMB Planejament GIS | https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament/Expedients/MapServer/3 | Consulta `CODI_INE=08114` → **0** expedientes con geometría |

## Proyectos / expedientes

- **Exposición pública:** https://www.gavaciutat.cat/planejament-i-projectes-en-exposicio-publica (MPPGM claus 12/13b, PE Can Mas, modificación PP Pla de Ponent, etc.).
- **Planejament aprovat:** índice a plans parcials, especials, estudis de detall, modificacions PGM.
- **Detalle:** páginas Liferay bajo `/ciutat/urbanisme-i-obres/…` con documentos en `/documents/20142/…/*.pdf`.
- **Formato:** HTML Liferay + biblioteca documental; títulos en `<title>`; PDFs por actuación.

## Licencias

- No hay listado público de **concesiones** fechadas en el tablón local (solo taxas/ordenanzas urbanísticas).
- El **catálogo STA** publica trámites (`Llicència d'obra menor`, certificados urbanísticos, disciplina, etc.) — filas informativas para `licencias.jsonl`.
- Trámite enlazado desde web: licencias/comunicaciones vía sede (p. ej. catálogo general PTS_HOME).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes probadas:**
  - AMB `Planejament/Expedients/MapServer/3` con `CODI_INE=08114` → sin features.
  - `agendaurbana.gava.cat` → no responde en el entorno del agente (sin ArcGIS REST documentado).
  - No se localizó WFS/ArcGIS público con campo de expediente enlazable al listado Liferay.
- **Estrategia:** ingestión solo metadatos + PDFs; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** visor municipal posiblemente en red interna o con protección; expedientes en PDF sin georreferencia explícita.

## Limitaciones generales

- Certificado SSL de `eseu.gava.cat` requiere `sede_insecure_ssl: true` en el adapter (patrón Getafe).
- Crawl Liferay limitado a ~45 páginas semilla urbanísticas.
- Sin boletín BOCM asociado en cola (`bocm_count: 0`).
