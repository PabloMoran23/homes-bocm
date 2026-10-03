"use client";

import dynamic from "next/dynamic";
import styles from "./Directory.module.css";

export type DirectoryMapPoint = {
  name: string;
  center: [number, number];
  href?: string;
};

export type DirectoryMapProps = {
  points: DirectoryMapPoint[];
  label: string;
  local?: boolean;
};

const MapCanvas = dynamic(() => import("./DirectoryMapCanvas"), {
  ssr: false,
  loading: () => (
    <div className={styles.mapLoading} role="status">
      Cargando cartografía…
    </div>
  ),
});

export function DirectoryMap(props: DirectoryMapProps) {
  return (
    <div className={styles.mapFrame}>
      <div className={styles.mapEyebrow}>
        <span />
        {props.local ? "Entorno del municipio" : "Una mirada al territorio"}
      </div>
      <MapCanvas {...props} />
      <div className={styles.mapCaption}>
        <span className={styles.mapDot} />
        {props.label}
      </div>
    </div>
  );
}
