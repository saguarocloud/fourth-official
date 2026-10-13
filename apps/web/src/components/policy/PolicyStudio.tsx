"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/shell/AppShell";
import type { PolicyChange, PolicyHistory, TenantPolicy } from "@/contracts/policyHistory";
import { PARTNERS } from "@/domain/broadcast";
import {
  changesOf,
  EDITABLE_FIELDS,
  type FieldChange,
  utcTime,
  versionLine,
} from "@/domain/policy";
import { plural } from "@/lib/plural";

import { PolicyEditor } from "./PolicyEditor";
import { type Lookup, resetPolicies, usePolicyHistory } from "./usePolicyHistory";

const DEFAULT_PARTNER = PARTNERS[0]!.id;
const RESET_REASON = "Back to the release";

const ACTION_NAMES: Readonly<Record<PolicyChange["action"], string>> = {
  bundled: "Release",
  edited: "Edited",
  reset: "Reset",
};

function Ledger({
  history,
  selected,
  drafting,
  onSelect,
}: {
  readonly history: PolicyHistory;
  readonly selected: number;
  readonly drafting: boolean;
  readonly onSelect: (version: number) => void;
}) {
  const changes = [...history.changes].reverse();
  return (
    <nav aria-labelledby="versions-heading" className="ledger">
      <h2 id="versions-heading" className="panel-heading ledger__heading">
        Versions · {history.versions.length}
      </h2>
      {drafting && (
        <p className="ledger__draft">
          <span className="ledger__version">
            Version {(changes[0] as PolicyChange).version + 1}
          </span>
          <span className="ledger__action">Unsaved</span>
        </p>
      )}
      <ol aria-label="Versions" className="ledger__list">
        {changes.map((change) => (
          <li key={change.version}>
            <button
              type="button"
              className="ledger__entry"
              aria-current={change.version === selected ? "true" : undefined}
              onClick={() => onSelect(change.version)}
            >
              <span className="ledger__version">Version {change.version}</span>
              <span className="ledger__action">{ACTION_NAMES[change.action]}</span>
              <span className="ledger__line">{versionLine(change)}</span>
              {change.fields.length > 0 && (
                <span className="ledger__fields">
                  {plural(change.fields.length, "field", "fields")} changed
                </span>
              )}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

// A list says what it gained and lost, so nobody compares two lists by eye; a single value
// reads as it now stands, beside the struck value it replaced.
function Change({ change }: { readonly change: FieldChange }) {
  if (!change.added || !change.removed) return change.after;
  return (
    <ul className="version__delta">
      {change.added.map((item) => (
        <li key={`+${item}`} className="version__added">
          <span aria-hidden="true">+ </span>
          <span className="sr-only">Added: </span>
          {item}
        </li>
      ))}
      {change.removed.map((item) => (
        <li key={`-${item}`} className="version__removed">
          <span aria-hidden="true">− </span>
          <span className="sr-only">Removed: </span>
          {item}
        </li>
      ))}
    </ul>
  );
}

function VersionView({
  history,
  version,
  onEdit,
}: {
  readonly history: PolicyHistory;
  readonly version: number;
  readonly onEdit: () => void;
}) {
  const index = history.versions.findIndex((v) => v.version === version);
  const policy = history.versions[index] as TenantPolicy;
  const change = history.changes[index] as PolicyChange;
  const before = index > 0 ? history.versions[index - 1] : undefined;
  const current = index === history.versions.length - 1;
  const changed = before ? changesOf(before, policy) : [];
  return (
    <section aria-labelledby="version-heading" className="version">
      <div className="version__head">
        <h2 id="version-heading" className="version__title">
          Version {version}
          {current && <span className="version__current"> · current</span>}
        </h2>
        {current && (
          <button type="button" className="key" data-intent="primary" onClick={onEdit}>
            <span>Edit this policy</span>
          </button>
        )}
        <p className="version__line">{versionLine(change)}</p>
      </div>
      {before ? (
        <table className="version__changes">
          <caption className="sr-only">What version {version} changed</caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Version {before.version}</th>
              <th scope="col">Version {version}</th>
            </tr>
          </thead>
          <tbody>
            {changed.map((c) => (
              <tr key={c.field}>
                <th scope="row">{c.label}</th>
                <td className={c.added ? "version__was" : "version__before"}>{c.before}</td>
                <td className="version__after">
                  <Change change={c} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="version__note">The oldest version kept. The policy as it stood:</p>
      )}
      <dl className="version__policy" aria-label={`Version ${version} in full`}>
        {EDITABLE_FIELDS.map(({ field, label, read }) => (
          <div key={field}>
            <dt>{label}</dt>
            <dd>{read(policy[field])}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ResetKey({ onReset }: { readonly onReset: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const keep = useRef<HTMLButtonElement>(null);
  const opened = useRef(false);

  // The keyboard goes into the confirmation when it opens, and back to the key when it closes.
  useEffect(() => {
    if (confirming) keep.current?.focus();
    else if (opened.current) trigger.current?.focus();
    opened.current = confirming;
  }, [confirming]);

  async function reset() {
    if (busy) return;
    setBusy(true);
    const outcome = await resetPolicies(RESET_REASON);
    setBusy(false);
    setConfirming(false);
    if (outcome.ok) {
      setFailure(null);
      onReset();
    } else setFailure(outcome.detail);
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && !busy) setConfirming(false);
  }

  return (
    <div className="reset">
      {confirming ? (
        <div
          role="group"
          aria-label="Reset to the release"
          className="reset__confirm"
          onKeyDown={onKey}
        >
          <p>
            All {PARTNERS.length} partners go back to the release&apos;s policy as a new version;
            the ledger keeps every earlier version.
          </p>
          <button
            type="button"
            className="key"
            data-intent="danger"
            disabled={busy}
            onClick={() => void reset()}
          >
            <span>{busy ? "Resetting…" : "Reset every partner"}</span>
          </button>
          <button
            ref={keep}
            type="button"
            className="key"
            data-intent="quiet"
            disabled={busy}
            onClick={() => setConfirming(false)}
          >
            <span>Keep the policies</span>
          </button>
        </div>
      ) : (
        <button
          ref={trigger}
          type="button"
          className="key"
          data-intent="danger"
          onClick={() => setConfirming(true)}
        >
          <RotateCcw aria-hidden="true" strokeWidth={1.75} />
          <span>Reset to the release</span>
        </button>
      )}
      {failure && (
        <p role="alert" className="policy-refusal">
          {failure}
        </p>
      )}
    </div>
  );
}

function Verdict({ lookup, name }: { readonly lookup: Lookup; readonly name: string }) {
  let tone = "neutral";
  let text = "Reading the partner's policy.";
  if (lookup.status === "unavailable") {
    tone = "red";
    text = "The policy service did not answer. Nothing has changed; try again.";
  } else if (lookup.status === "ready") {
    const latest = lookup.history.changes.at(-1) as PolicyChange;
    const how =
      latest.action === "bundled"
        ? "as shipped with the release"
        : `${latest.action === "reset" ? "reset" : "edited"} by ${latest.editor} at ${utcTime(latest.changedAt)} UTC: ${plural(latest.fields.length, "field", "fields")} changed`;
    tone = "green";
    text = `${name} is on version ${latest.version}, ${how}. Changes apply from the next item.`;
  }
  return (
    <p role="status" aria-label="Policy verdict" className="verdict" data-tone={tone}>
      <span aria-hidden="true" className="verdict__lamp" />
      {text}
    </p>
  );
}

function Desk({
  tenantId,
  history,
  reload,
}: {
  readonly tenantId: string;
  readonly history: PolicyHistory;
  readonly reload: () => void;
}) {
  const current = (history.versions.at(-1) as TenantPolicy).version;
  const [selected, setSelected] = useState(current);
  const [editing, setEditing] = useState(false);
  const shown = history.versions.some((v) => v.version === selected) ? selected : current;
  const policy = history.versions.at(-1) as TenantPolicy;
  return (
    <div className="policy-desk">
      <Ledger
        history={history}
        selected={shown}
        drafting={editing}
        onSelect={(v) => {
          setSelected(v);
          setEditing(false);
        }}
      />
      {editing ? (
        <PolicyEditor
          tenantId={tenantId}
          policy={policy}
          dutyEditor={policy.dutyEditor}
          onSaved={(version) => {
            setEditing(false);
            setSelected(version);
            reload();
          }}
          onCancel={() => setEditing(false)}
          onReload={() => {
            setEditing(false);
            reload();
          }}
        />
      ) : (
        <VersionView history={history} version={shown} onEdit={() => setEditing(true)} />
      )}
    </div>
  );
}

/** Policy Studio: each partner's policy as a ledger of versions, what each changed, and the next
 * one written from a form or raw YAML (ADR-015). */
export function PolicyStudio() {
  const params = useSearchParams();
  const asked = params.get("partner");
  const partner =
    PARTNERS.find((p) => p.id === asked) ?? PARTNERS.find((p) => p.id === DEFAULT_PARTNER)!;
  const { lookup, reload } = usePolicyHistory(partner.id);
  return (
    <AppShell current="/policy" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Policy Studio</h1>
        <Verdict lookup={lookup} name={partner.name} />
      </header>
      <div className="policy-controls">
        <nav aria-label="Partners">
          <ul className="partner-keys">
            {PARTNERS.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/policy?partner=${p.id}`}
                  className="partner-key policy-partner"
                  aria-current={p.id === partner.id ? "page" : undefined}
                  scroll={false}
                >
                  <span aria-hidden="true" className="partner-key__cap policy-partner__cap">
                    {p.code}
                  </span>
                  <span className="policy-partner__name">{p.name}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <ResetKey onReset={reload} />
      </div>
      {lookup.status === "ready" ? (
        <Desk key={partner.id} tenantId={partner.id} history={lookup.history} reload={reload} />
      ) : (
        lookup.status === "unavailable" && (
          <button type="button" className="key" data-size="sm" onClick={reload}>
            <span>Try again</span>
          </button>
        )
      )}
      <p className="page-footnote policy-footnote">
        All data is synthetic. This demo has no sign-in: an edit is recorded against the
        partner&apos;s duty editor, a named demo identity, and anyone can reset the policies to the
        release&apos;s.
      </p>
    </AppShell>
  );
}
