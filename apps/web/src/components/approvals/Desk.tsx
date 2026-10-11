import { useEffect, useRef } from "react";

import { ProgramMonitor } from "@/components/broadcast/ProgramMonitor";
import type { TenantInfo } from "@/components/matchday/useTenants";
import type { TenantItemEntry } from "@/contracts/feed";
import { correctedSince, englishVersion } from "@/domain/approvals";
import { type BroadcastState, PARTNERS, preview } from "@/domain/broadcast";
import { REASON_MAX } from "@/lib/decision";

const CORRECTED_REASON = "A correction changed this item's facts";

export interface DeskActions {
  /** Keys and buttons wait: full time, a request in flight, the run not known, or settling. */
  readonly blocked: boolean;
  readonly busy: boolean;
  readonly rejecting: boolean;
  readonly reasonError: string | null;
  /** Move focus to the desk when it shows a new item (not on the page's first view). */
  readonly focusOnShow: boolean;
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
        {item.rendered?.claims.map((claim, n) => (
          <li key={n} lang={item.overlay.locale}>
            {claim}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Reject({ actions, prefill }: { actions: DeskActions; prefill: string }) {
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
        defaultValue={prefill}
        maxLength={REASON_MAX}
        autoComplete="off"
        readOnly={actions.busy}
        aria-invalid={actions.reasonError !== null}
        aria-describedby={actions.reasonError ? "reject-error" : undefined}
        onKeyDown={(event) => {
          if (event.key === "Escape") actions.onCancel();
        }}
      />
      {actions.reasonError && (
        <p id="reject-error" className="desk__error" role="alert">
          {actions.reasonError}
        </p>
      )}
      <div className="desk__reject-keys">
        <button type="submit" className="key" data-intent="danger" disabled={actions.busy}>
          <span>Send rejection</span>
        </button>
        <button type="button" className="key" aria-keyshortcuts="Escape" onClick={actions.onCancel}>
          <span>
            <span className="key-cap" aria-hidden="true">
              Esc
            </span>
            Cancel
          </span>
        </button>
      </div>
    </form>
  );
}

/** The held item as it will air on its partner, read against English, with why it waits and the
 * editor's two keys. */
export function Desk({ item, view, tenant, actions }: DeskProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const rejectKey = useRef<HTMLButtonElement>(null);
  const wasRejecting = useRef(actions.rejecting);
  const { focusOnShow, rejecting } = actions;
  useEffect(() => {
    if (focusOnShow) heading.current?.focus();
  }, [focusOnShow]);
  useEffect(() => {
    // Putting the reason away returns the editor to the key that opened it.
    if (wasRejecting.current && !rejecting) rejectKey.current?.focus();
    wasRejecting.current = rejecting;
  }, [rejecting]);

  const partner = PARTNERS.find((p) => p.id === item.tenantId);
  if (partner === undefined) {
    return (
      <section className="desk" aria-label="Unknown partner">
        <p className="desk__unknown">
          This item belongs to a partner this studio does not know. It cannot be decided here.
        </p>
      </section>
    );
  }
  const english = englishVersion(view, item);
  const corrected = correctedSince(view, item);
  const evidence = new Set(item.localized?.claims.flatMap((c) => c.evidence.eventIds) ?? []);
  const editor = tenant?.dutyEditor;
  const headline = item.rendered?.headline ?? "";
  return (
    <section className="desk" aria-labelledby="desk-heading">
      <h2 id="desk-heading" className="sr-only" ref={heading} tabIndex={-1}>
        {`${partner.name}: ${headline}`}
      </h2>
      <div className="desk__stage">
        <ProgramMonitor
          partner={partner}
          program={preview(view, partner.id, item.localized?.insightId ?? "")}
          mode="preview"
          clock={view.clock}
          guides={false}
          stageLabel={`${partner.name} preview: the held graphic as it would air. Its words are on this desk as text.`}
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
          <p>{`${partner.name}'s policy sends every ${item.itemKind} to an editor before it airs.`}</p>
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
          disabled={actions.blocked || corrected || rejecting}
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
          ref={rejectKey}
          aria-keyshortcuts="R"
          aria-expanded={rejecting}
          disabled={actions.blocked}
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
      {rejecting && <Reject actions={actions} prefill={corrected ? CORRECTED_REASON : ""} />}
    </section>
  );
}
