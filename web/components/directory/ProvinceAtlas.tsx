"use client";
import Link from "next/link";
import { useState } from "react";
import Image from "next/image";
import styles from "./ProvinceAtlas.module.css";
export type AtlasProvince = {
  name: string;
  slug: string;
  href: string;
  municipalities: { name: string; href: string }[];
};
// Preserve the atlas reading order in a regular grid.
const provinceOrder = [
  "a-coruna",
  "asturias",
  "cantabria",
  "pontevedra",
  "leon",
  "palencia",
  "burgos",
  "zamora",
  "valladolid",
  "soria",
  "salamanca",
  "avila",
  "segovia",
  "madrid",
  "castello",
  "valencia",
  "illes-balears",
  "huelva",
  "sevilla",
  "cordoba",
  "jaen",
  "alacant",
  "cadiz",
  "malaga",
  "granada",
  "almeria",
  "santa-cruz-de-tenerife",
  "las-palmas",
];
const rank = (slug: string) => {
  const index = provinceOrder.indexOf(slug);
  return index < 0 ? provinceOrder.length : index;
};
const normalize = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
export function ProvinceAtlas({ provinces }: { provinces: AtlasProvince[] }) {
  const [query, setQuery] = useState("");
  const needle = normalize(query.trim());
  const sorted = [...provinces].sort(
    (a, b) => rank(a.slug) - rank(b.slug) || a.name.localeCompare(b.name, "es"),
  );
  const shown = sorted.filter(
    (p) =>
      normalize(p.name).includes(needle) ||
      p.municipalities.some((m) => normalize(m.name).includes(needle)),
  );
  return (
    <section aria-label="Provincias con información" className={styles.atlas}>
      <div className={styles.toolbar}>
        <span>Provincias con información</span>
        <label>
          <span className="sr-only">Busca una provincia o municipio</span>
          <input
            type="search"
            placeholder="Busca una provincia o municipio"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <ul className={styles.grid}>
        {shown.map((p) => (
          <li key={p.slug} className={styles.card}>
            <Link
              href={p.href}
              prefetch={false}
              className={styles.provinceLink}
            >
              <div className={styles.miniMap} aria-hidden="true">
                <Image src={`/maps/provinces/${p.slug}.webp`} alt="" width={520} height={260} loading="lazy" unoptimized />
              </div>
              <div className={styles.cardText}>
                <h2>{p.name}</h2>
                <p>
                  {p.municipalities.length}{" "}
                  {p.municipalities.length === 1
                    ? "municipio disponible"
                    : "municipios disponibles"}
                </p>
              </div>
            </Link>
            {needle && !normalize(p.name).includes(needle) && (
              <ul className={styles.matches}>
                {p.municipalities
                  .filter((m) => normalize(m.name).includes(needle))
                  .map((m) => (
                    <li key={m.href}>
                      <Link href={m.href} prefetch={false}>
                        {m.name} ↗
                      </Link>
                    </li>
                  ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
      {!shown.length && (
        <p role="status">No encontramos ese lugar. Prueba con otro nombre.</p>
      )}
      <p className={styles.attribution}>
        Cartografía: {" "}
        <a href="https://openmaptiles.org/">© OpenMapTiles</a> ·{" "}
        <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a>
      </p>
    </section>
  );
}
