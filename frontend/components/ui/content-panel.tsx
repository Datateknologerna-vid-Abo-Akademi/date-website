import type { ReactNode } from "react";

import styles from "./content-panel.module.css";

interface ContentPanelProps {
  children: ReactNode;
}

export function ContentPanel({ children }: ContentPanelProps) {
  return <section className={styles.panel}>{children}</section>;
}
