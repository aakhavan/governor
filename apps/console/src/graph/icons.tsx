import type { Kind } from "../api/types";

export function Mark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="11" cy="16" r="2" fill="currentColor" />
      <circle cx="21" cy="11" r="2" fill="currentColor" />
      <circle cx="21" cy="21" r="2" fill="currentColor" />
      <path d="M13 16 H19 M21 13 V19" fill="none" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  );
}

function KindMark({ kind }: { kind: Kind }) {
  switch (kind) {
    case "guard":
      return <path d="M16 21.2 19.2 22.4 V25.2c0 1.4-1.4 2.4-3.2 3.2-1.8-.8-3.2-1.8-3.2-3.2V22.4Z" fill="none" stroke="currentColor" strokeWidth="1.3" />;
    case "llm":
      return <path d="M16 6 V2.2 M13.2 2.2 H18.8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />;
    case "check":
      return <path d="M13 24.2 15.1 26.2 19.2 22" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />;
    case "dbt":
      return <path d="M12 22.4 H20 M12 24.4 H20 M12 26.4 H20" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
    case "gate":
      return <path d="M13 21.4 V27 M19 21.4 V27 M13 21.4 H19" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />;
    case "io":
      return <path d="M12.2 24 H16.2 M15 22.6 16.8 24 15 25.4 M19.8 24 H15.8 M17 22.6 15.2 24 17 25.4" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />;
    case "summary":
      return (
        <>
          <circle cx="13.2" cy="24" r="0.8" fill="currentColor" />
          <circle cx="16" cy="24" r="0.8" fill="currentColor" />
          <circle cx="18.8" cy="24" r="0.8" fill="currentColor" />
        </>
      );
    default: {
      const unreachable: never = kind;
      void unreachable;
      return null;
    }
  }
}

export function KindIcon({ kind }: { kind: Kind }) {
  return (
    <svg className="kind-icon" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="8" y="6" width="16" height="13" rx="3.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="13" cy="12" r="1.15" fill="currentColor" />
      <circle cx="19" cy="12" r="1.15" fill="currentColor" />
      <path d="M13 16.2 H19" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <rect x="11" y="20.2" width="10" height="7" rx="1.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <KindMark kind={kind} />
    </svg>
  );
}

export function DoneMark() {
  return (
    <svg className="done-mark" viewBox="0 0 12 12" aria-hidden="true">
      <path d="M2 6.2 4.7 8.8 10 3.2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
