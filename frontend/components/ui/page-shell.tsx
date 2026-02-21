import type { ReactNode } from "react";

import styles from "./page-shell.module.css";

interface PageShellProps {
  children: ReactNode;
}

interface PageHeroProps {
  title: string;
  eyebrow?: string;
  meta?: ReactNode;
  children?: ReactNode;
}

interface PagePanelProps {
  children: ReactNode;
}

export function PageShell({ children }: PageShellProps) {
  return <div className={styles.shell}>{children}</div>;
}

export function PageHero({ title, eyebrow, meta, children }: PageHeroProps) {
  return (
    <section className={styles.hero}>
      {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
      <h1>{title}</h1>
      {meta ? <p className={styles.meta}>{meta}</p> : null}
      {children}
    </section>
  );
}

export function PagePanel({ children }: PagePanelProps) {
  return <section className={styles.panel}>{children}</section>;
}
