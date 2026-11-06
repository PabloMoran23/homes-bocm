# Esparreguera — investigación portal (urbanismo / licencias)

## Web y semillas

- **Web municipal:** [https://www.esparreguera.cat/](https://www.esparreguera.cat/) — menú **Urbanisme** con enllaç a la seu.
- **Seu electrònica:** [https://seu.esparreguera.cat/](https://seu.esparreguera.cat/)
  - **Registre de publicacions (últims):** `/registrePublic/ultims` — taula HTML amb Data / Acció / Títol / Tipus (filtratge urbà al codi).
  - **Instruments de planificació urbanística (categoria 7):** `/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=7` — blocs `dElementPublicacioDefecte` amb enllaç a fitxa o PDF.
  - **Cercadors dins la categoria urbanisme:** `/urbanismeCategoriaPublic/cercadorCategoria/{id}` (ids vists al menú lateral: 35, 36, 37, 8, 32, 33, 34).
- **Tràmits (informació):** [https://tramits.esparreguera.cat](https://tramits.esparreguera.cat)
- **Tauler d’anuncis electrònic (índex seu):** `/taulerAnuncisCategoriaPublic/index` — en aquest municipi la cerca textual (`/taulerAnuncisPublic/listPublicacions`) no retorna línies HTML parsejables sense paràmetres addicionals; l’**e-TAULER** consorciat es resol a [https://tauler.seu.cat/inici.do?idens=807650006](https://tauler.seu.cat/inici.do?idens=807650006) (app SPA; sense API estable per a scrape HTTP simple).

## Cómo se listan expedientes / planeamiento

- **Llista principal:** HTML Semic (blocs per publicació o taula de registre), enllaços a `/registrePublic/registrePublicacio/{id}` o `/documentPublic/download/{id}` (PDF).
- **Patrón de datos:** mateix esquema que altres municipis catalans amb seu AOC (com Sitges): paginació `offset`/`max` als llistats urbanisme.

## Licencias de obra

- No hi ha un dataset obert de llicències amb llistat descarregable identificat en la seu com a “llista de llicències concedides”.
- Els **anuncis de llicències** podrien aparèixer al **tauler** (AOC) o com a publicacions puntuals; en aquest scrape s’extreuen fileres del **registre** quan el títol/categoria mencionen llicència/obra en context urbà.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes relacionadas (catàleg oficial cartografia planejament, no lligades per codi d’expedient en aquest adapter):**
  - **MUC Visor** (Generalitat): `https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08076&set-locale=ca` — cartografia urbanística per municipi INE **08076** (TLS; en alguns entorns la connexió pot fallar).
  - **RPUC** (Registre planejament urbanístic): `https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08076`
- **Estrategia en adapter:** cap consulta automàtica ArcGIS/WFS per fila; els expedients de la seu acostumen a ser PDFs o fitxes sense geometria embedida.
- **Limitaciones:** Sense enllaç estable expedient → geometria en la seu; el pipeline assignarà coordenades via geocodificació (centroide + jitter segons manifest).

## Limitaciones del scrape

- Registre `ultims` inclou molts tipus no urbans; s’aplica filtre per paraules clau d’urbanisme.
- e-TAULER és una SPA; no s’usa com a font principal sense API documentada.
