import type { ReactNode } from "react";

import styles from "./auth-shell.module.css";

interface AuthShellProps {
  title: string;
  children: ReactNode;
  narrow?: boolean;
}

export function AuthShell({ title, children, narrow = false }: AuthShellProps) {
  return (
    <div className={`${styles.page} ${narrow ? styles.pageNarrow : ""}`} data-testid="auth-shell">
      <div className={styles.card} data-testid="auth-shell-card">
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}
