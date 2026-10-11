import { useEffect, useRef } from "react";

import { ProgramMonitor } from "@/components/broadcast/ProgramMonitor";
import type { TenantInfo } from "@/components/matchday/useTenants";
import type { TenantItemEntry } from "@/contracts/feed";
import { correctedSince, englishVersion } from "@/domain/approvals";
import { type BroadcastState, PARTNERS, preview } from "@/domain/broadcast";
import { REASON_MAX } from "@/lib/decision";

const KIND_NAMES: Readonly<Record<string, string>> = { insight: "insight", recap: "recap" };

export interface DeskActions {
  readonly closed: boolean;
  readonly busy: boolean;
  readonly rejecting: boolean;
  readonly reasonError: string | null;
  readonly onApprove: () => void;
  readonly onReject: () => void;
  readonly onCancel: () => void;
  readonly onSendReject: (reason: string) => void;
}

interface DeskProps {
  readonly item: TenantItemEntry;
  readonly view: BroadcastState;
  readonly tenant: TenantInfo | undefined;
  readonly actions: DeskActions;
}

function Words({ item, label }: { item: TenantItemEntry; label: string }) {
  return (
    <section className="desk__read" aria-label={label}>
      <h3 className="panel-heading">{label}</h3>
      <p className="desk__headline" lang={item.overlay.locale}>
        {item.rendered?.headline}
      </p>
      <ul className="desk__claims">
        {item.rendered?.claims.map((claim) => (
          <li key={claim} lang={item.overlay.locale}>
            {claim}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Reject({ actions }: { actions: DeskActions }) {
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => field.current?.focus(), []);
  return (
    <form
      className="desk__reject"
      onSubmit={(event) => {
        event.preventDefault();
        actions.onSendReject(field.current?.value ?? "");
      }}
    >
      <label htmlFor="reject-reason">Reason for rejecting</label>
      <input
        id="reject-reason"
        ref={field}
        maxLength={REASON_MAX}
        autoComplete="off"
        aria-invalid={actions.reasonError !== null}
        aria-describedby={actions.reasonError ? "reject-error" : undefined}
        onKeyDown={(event) => {
          if (event.key === "Escape") actions.onCancel();
        }}
      />
      {actions.reasonError && (
        <p id="reject-error" className="desk__error">
          {actions.reasonError}
        </p>
      )}
      <button type="submit" className="key" data-intent="danger" disabled={actions.busy}>
        <span>Send rejection</span>
      </button>
    </form>
  );
}

/** The held item as it will air on its partner, read against English, with why it waits and the
 * editor's two keys. */
export function Desk({ item, view, tenant, actions }: DeskProps) {
  const partner = PARTNERS.find((p) => p.id === item.tenantId) ?? PARTNERS[0]!;
  const insightId = item.localized?.insightId ?? "";
  const english = englishVersion(view, item);
  const corrected = correctedSince(view, item);
  const evidence = new Set(item.localized?.claims.flatMap((c) => c.evidence.eventIds) ?? []);
  const kind = KIND_NAMES[item.itemKind] ?? item.itemKind;
  const editor = tenant?.dutyEditor;
  const blocked = actions.closed || actions.busy;
  return (
    <section className="desk" aria-labelledby="desk-heading">
      <h2 id="desk-heading" className="sr-only">
        {`${partner.name}: ${item.rendered?.headline ?? ""}`}
      </h2>
      <div className="desk__stage">
        <ProgramMonitor
          partner={partner}
          program={preview(view, partner.id, insightId)}
          mode="preview"
          clock={view.clock}
          guides={false}
        />
      </div>
      <div className="desk__reading">
        {english ? (
          <Words item={english} label="In English" />
        ) : (
          <Words item={item} label="As written" />
        )}
        <section className="desk__why" aria-label="Why it waits">
          <h3 className="panel-heading">Why it waits</h3>
          <p>{`${partner.name}'s policy sends every ${kind} to an editor before it airs.`}</p>
          <p>
            {`It rests on ${evidence.size} match ${evidence.size === 1 ? "event" : "events"}, checked twice: once in English, then in ${partner.language}.`}
          </p>
          {corrected && (
            <p className="desk__corrected">
              A correction has since changed this item&apos;s facts. It cannot air; reject it with
              the correction as the reason.
            </p>
          )}
        </section>
      </div>
      <div className="desk__keys">
        <button
          type="button"
          className="key"
          data-intent="primary"
          aria-keyshortcuts="A"
          disabled={blocked || corrected}
          onClick={actions.onApprove}
        >
          <span>
            <span className="key-cap" aria-hidden="true">
              A
            </span>
            {editor ? `Approve as ${editor}` : "Approve"}
          </span>
        </button>
        <button
          type="button"
          className="key"
          aria-keyshortcuts="R"
          aria-expanded={actions.rejecting}
          disabled={blocked}
          onClick={actions.onReject}
        >
          <span>
            <span className="key-cap" aria-hidden="true">
              R
            </span>
            Reject…
          </span>
        </button>
        <p className="desk__identity">
          {editor
            ? `${editor} is ${partner.name}'s duty editor (demo identity): this demo has no sign-in.`
            : "Decisions are recorded against the partner's duty editor (demo identity)."}
        </p>
      </div>
      {actions.rejecting && !blocked && <Reject actions={actions} />}
    </section>
  );
}
