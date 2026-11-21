import type { ReactNode } from "react";

export function ViewFrame({
  caption,
  empty,
  children,
}: {
  caption: string;
  empty?: string | null;
  children?: ReactNode;
}) {
  return (
    <div className="view">
      <p className="view-caption">{caption}</p>
      {empty ? <p className="empty">{empty}</p> : children}
    </div>
  );
}
