import type { ReactNode } from "react";

interface EventDetailShellProps {
  pageClassName: string;
  backgroundClassName: string;
  containerClassName: string;
  backgroundImageUrl?: string | null;
  children: ReactNode;
}

export function EventDetailShell({
  pageClassName,
  backgroundClassName,
  containerClassName,
  backgroundImageUrl,
  children,
}: EventDetailShellProps) {
  return (
    <div className={pageClassName}>
      <div
        className={backgroundClassName}
        style={backgroundImageUrl ? { backgroundImage: `url(${backgroundImageUrl})` } : undefined}
      >
        <div className="container-md min-vh-100 p-1 event-detail-shell">
          <div className={containerClassName}>{children}</div>
        </div>
      </div>
    </div>
  );
}
