import type { ReactNode } from "react";

import { NavRail } from "@/components/shell/NavRail";
import { TopBar } from "@/components/shell/TopBar";
import type { MatchdaySummary } from "@/domain/matchday";

interface AppShellProps {
  readonly current: string;
  /** The matchday readouts in the top bar; screens without them omit it. */
  readonly summary?: MatchdaySummary;
  readonly studio: string;
  readonly replay: boolean;
  readonly rail?: ReactNode;
  readonly children: ReactNode;
}

/** Gallery layout: status bar across the top, screens on the left, live rail on the right. */
export function AppShell({ current, summary, studio, replay, rail, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <TopBar summary={summary} studio={studio} replay={replay} />
      <NavRail current={current} />
      <main id="main" className="app-shell__main" tabIndex={-1}>
        {children}
      </main>
      {rail && (
        <aside className="app-shell__rail" aria-label="Live rail">
          {rail}
        </aside>
      )}
    </div>
  );
}
