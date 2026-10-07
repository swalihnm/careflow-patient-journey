export function Loading() {
  return <div className="loading">Loading…</div>;
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>;
}

export function Forbidden({ requiredRoles }: { requiredRoles: string }) {
  return (
    <div className="error-banner">
      The role currently selected in the sidebar can&apos;t view this page. This view requires: {requiredRoles}.
      Switch roles using the selector at the bottom of the sidebar.
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
