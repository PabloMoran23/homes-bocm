# Andújar — investigación portal ayuntamiento

| Fuente | URL |
|--------|-----|
| Web municipal (TYPO3) | https://www.andujar.es |
| Área urbanismo | https://www.andujar.es/areas-municipales/servicios-infraestructuras-y-urbanismo |
| Noticias urbanismo (`tx_news_pi1`) | https://www.andujar.es/areas-municipales/servicios-infraestructuras-y-urbanismo?tx_news_pi1=266 |
| Sede electrónica | https://sede.andujar.es |
| Catálogo trámites sede | https://sede.andujar.es/Editors/DlgTramiteSede.aspx |
| BOJA (publicaciones ayto.) | https://www.juntadeandalucia.es/boja/ |
| SITUADIFUSION (planeamiento JA) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |
| VITUA (cartografía regional) | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ |
| Tablón Diputación Jaén | https://sede.dipujaen.es/Tablon |

## Urbanismo / expedientes

- **CMS web:** TYPO3 con menú *Servicios, Infraestructuras y Urbanismo* (subsecciones Urbanismo, Proyectos en marcha, disciplina). Noticias vía extensión `tx_news`.
- **Planeamiento:** instrumentos y anuncios de información pública se publican en **BOJA** (p. ej. sector NS-2 del PGOU, expediente `EAE-JA-010/2015`; innovación PGOU 2023). Enlace a documentación en Google Drive desde anuncios BOJA.
- **Sede:** plataforma propia (ASP.NET). Trámites destacados incluyen *Procedimiento Urbanístico* y licencias (alteración de fincas, apertura de establecimientos, ocupación dominio público). **Mis expedientes** requiere identificación; no hay API pública tipo espublico `/board` verificada.
- **Edictos:** enlace *Edictos y Anuncios* en portada sede; estructura HTML no confirmada en entorno cloud (timeout TLS hacia `*.andujar.es`).

## Licencias

- No hay listado público de concesiones georreferenciadas.
- Catálogo de trámites sede + páginas informativas del área de urbanismo.
- Adapter ingiere filas informativas de trámites y enriquece con tablón provincial si aparece en futuras iteraciones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** VITUA (clasificación/calificación suelo a escala municipal/regional); SITUADIFUSION (PDF/planos digitalizados, sin GeoJSON por expediente). No se localizó visor ArcGIS municipal ni WFS del ayuntamiento enlazado a códigos de expediente.
- **Estrategia:** metadatos de planeamiento desde BOJA + enlaces SITUA/VITUA; coordenadas vía geocode (centroide municipal + jitter). Sin `geom_geojson` en adapter.
- **Limitaciones:** portales `www.andujar.es` / `sede.andujar.es` inaccesibles desde algunos entornos (handshake TLS timeout); validación local/CI recomendada. Expedientes individuales no georreferenciados en fuentes abiertas.

## Limitaciones generales

- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
- SSL/TLS hacia dominios municipales puede fallar fuera de la red del ayuntamiento.
- Paginación TYPO3 manual; BOJA sin buscador estable (404 en URL probada).
