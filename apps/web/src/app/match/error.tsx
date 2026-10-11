"use client";

import { AppShell } from "@/components/shell/AppShell";
import { KeyButton } from "@/components/ui/KeyButton";

interface MatchLiveErrorProps {
  readonly error: Error & { digest?: string };
  readonly retry: () => void;
}

/** A feed the screen cannot draw stops this screen, not the studio: say so and offer a retry. */
export default function MatchLiveError({ retry }: MatchLiveErrorProps) {
  return (
    <AppShell current="/match" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Match Live</h1>
        <p role="alert" className="verdict" data-tone="red">
          <span aria-hidden="true" className="verdict__lamp" />
          The live feed could not be shown. Nothing was published from this screen.
        </p>
      </header>
      <KeyButton intent="primary" onClick={retry}>
        Try again
      </KeyButton>
    </AppShell>
  );
}
