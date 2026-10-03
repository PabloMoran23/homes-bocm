"use client";

import Link from "next/link";
import { useId, useState } from "react";
import styles from "./Directory.module.css";

export type DirectoryPlace = { name: string; href: string; caption: string };
const normalize = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

export function DirectoryPlaces({
  places,
  searchPlaces = places,
  title,
  placeholder,
}: {
  places: DirectoryPlace[];
  searchPlaces?: DirectoryPlace[];
  title: string;
  placeholder: string;
}) {
  const [query, setQuery] = useState("");
  const id = useId();
  const needle = normalize(query.trim());
  const shown = needle
    ? searchPlaces.filter((p) =>
        normalize(`${p.name} ${p.caption}`).includes(needle),
      )
    : places;
  return (
    <section
      id="lugares"
      className={styles.placesSection}
      aria-labelledby={`${id}-heading`}
    >
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>Explora a tu ritmo</span>
          <h2 id={`${id}-heading`}>{title}</h2>
        </div>
        <div className={styles.searchField}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m16 16 4.5 4.5" />
          </svg>
          <label className="sr-only" htmlFor={id}>
            {placeholder}
          </label>
          <input
            id={id}
            type="search"
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {needle ? `${shown.length} lugares encontrados` : ""}
      </p>
      <ul className={styles.placesGrid}>
        {shown.map((place) => (
          <li key={place.href}>
            <Link
              prefetch={false}
              href={place.href}
              className={styles.placeLink}
            >
              <div>
                <h3>{place.name}</h3>
                <p>{place.caption}</p>
              </div>
              <span aria-hidden="true">↗</span>
            </Link>
          </li>
        ))}
      </ul>
      {shown.length === 0 ? (
        <div className={styles.emptyState}>
          <p>No encontramos ese lugar.</p>
          <span>Prueba otro nombre o explora las provincias.</span>
          <button onClick={() => setQuery("")}>Volver al listado</button>
        </div>
      ) : null}
    </section>
  );
}
