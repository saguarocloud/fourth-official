"use client";

import { type KeyboardEvent, useRef, useState } from "react";

import type { TenantPolicy } from "@/contracts/policyHistory";
import { toYaml } from "@/domain/policy";

import { PolicyForm, problemsOf } from "./PolicyForm";
import { type EditBody, saveEdit } from "./usePolicyHistory";

const CONFLICT = 409;
const MAX_REASON = 200;
const TABS = ["form", "raw"] as const;
type Tab = (typeof TABS)[number];
const TAB_NAMES: Readonly<Record<Tab, string>> = { form: "Form", raw: "Raw YAML" };

interface PolicyEditorProps {
  readonly tenantId: string;
  readonly policy: TenantPolicy;
  readonly dutyEditor: string;
  readonly onSaved: (version: number) => void;
  readonly onCancel: () => void;
  readonly onReload: () => void;
}

interface Refusal {
  readonly status: number;
  readonly lines: readonly string[];
}

// The tab the arrow, Home and End keys move to, as the ARIA tabs pattern has it.
function tabFor(key: string, from: Tab): Tab | null {
  const at = TABS.indexOf(from);
  if (key === "ArrowRight") return TABS[(at + 1) % TABS.length]!;
  if (key === "ArrowLeft") return TABS[(at - 1 + TABS.length) % TABS.length]!;
  if (key === "Home") return TABS[0];
  if (key === "End") return TABS[TABS.length - 1]!;
  return null;
}

/** The partner's next version, from the form or the raw YAML, with the reason it is made. The
 * form and the raw view share one draft: the raw view shows the form's edits, and once the YAML
 * itself is edited it is what is saved until those edits are discarded. */
export function PolicyEditor({
  tenantId,
  policy,
  dutyEditor,
  onSaved,
  onCancel,
  onReload,
}: PolicyEditorProps) {
  // The version this draft was made on, even if the policy moves on while it is open: the API
  // then refuses it as stale instead of it overwriting the newer version.
  const [base] = useState(policy.version);
  const [view, setView] = useState<Tab>("form");
  const [draft, setDraft] = useState(policy);
  const [raw, setRaw] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const reasonField = useRef<HTMLInputElement>(null);
  const tabs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({});
  const next = base + 1;

  function onTabKey(event: KeyboardEvent<HTMLButtonElement>, from: Tab) {
    const to = tabFor(event.key, from);
    if (!to) return;
    event.preventDefault();
    setView(to);
    tabs.current[to]?.focus();
  }

  async function save() {
    const why = reason.trim();
    if (why.length === 0) {
      setRefusal({
        status: 0,
        lines: ["Say why you are making this version: the ledger records it."],
      });
      reasonField.current?.focus();
      return;
    }
    const problems = raw === null ? problemsOf(draft) : [];
    if (problems.length > 0) {
      setRefusal({ status: 0, lines: problems });
      return;
    }
    setSaving(true);
    setRefusal(null);
    const edit: EditBody =
      raw === null
        ? { policy: { ...draft }, baseVersion: base, reason: why }
        : { yaml: raw, baseVersion: base, reason: why };
    const outcome = await saveEdit(tenantId, edit);
    setSaving(false);
    if (outcome.ok) onSaved(outcome.change.version);
    else setRefusal({ status: outcome.status, lines: [outcome.detail] });
  }

  return (
    <section aria-labelledby="editor-heading" className="policy-editor">
      <div className="policy-editor__head">
        <h2 id="editor-heading" className="policy-editor__title">
          Version {next}
          <span className="version__current"> · draft from version {base}</span>
        </h2>
        <p className="policy-editor__who">
          Recorded against {dutyEditor} (demo identity). It governs the next item.
        </p>
      </div>
      <div role="tablist" aria-label="How to edit" className="policy-tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            ref={(element) => {
              tabs.current[tab] = element;
            }}
            type="button"
            role="tab"
            id={`policy-tab-${tab}`}
            aria-selected={view === tab}
            aria-controls={`policy-panel-${tab}`}
            tabIndex={view === tab ? 0 : -1}
            className="policy-tab"
            onClick={() => setView(tab)}
            onKeyDown={(event) => onTabKey(event, tab)}
          >
            {TAB_NAMES[tab]}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="policy-panel-form"
        aria-labelledby="policy-tab-form"
        hidden={view !== "form"}
        className="policy-panel"
      >
        {raw === null ? (
          <PolicyForm draft={draft} onChange={setDraft} />
        ) : (
          <div className="policy-notice">
            <p>
              The raw YAML has edits the form cannot show. Saving saves the YAML; discard its edits
              to use the form again.
            </p>
            <button
              type="button"
              className="key"
              data-size="sm"
              data-intent="quiet"
              onClick={() => setRaw(null)}
            >
              <span>Discard the YAML edits</span>
            </button>
          </div>
        )}
      </div>
      <div
        role="tabpanel"
        id="policy-panel-raw"
        aria-labelledby="policy-tab-raw"
        hidden={view !== "raw"}
        className="policy-panel policy-field"
      >
        <label htmlFor="policy-raw" className="policy-field__label">
          The policy as YAML
        </label>
        <p id="policy-raw-hint" className="policy-field__hint">
          Read strictly, as a policy file is. The partner, its locale and its duty editor stay as
          they are.
        </p>
        <textarea
          id="policy-raw"
          className="policy-raw"
          value={raw ?? toYaml(draft)}
          spellCheck={false}
          rows={24}
          aria-describedby="policy-raw-hint"
          onChange={(event) => setRaw(event.target.value)}
        />
      </div>
      <div className="policy-field">
        <label htmlFor="policy-reason" className="policy-field__label">
          Why <span className="policy-field__required">(required)</span>
        </label>
        <p id="policy-reason-hint" className="policy-field__hint">
          Recorded in the ledger with {dutyEditor}&apos;s name.
        </p>
        <input
          ref={reasonField}
          id="policy-reason"
          className="policy-input"
          value={reason}
          maxLength={MAX_REASON}
          aria-describedby="policy-reason-hint"
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      {refusal && (
        <div role="alert" className="policy-refusal">
          {refusal.lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
          {refusal.status === CONFLICT && (
            <button type="button" className="key" data-size="sm" onClick={onReload}>
              <span>Reload the latest version</span>
            </button>
          )}
        </div>
      )}
      <div className="policy-editor__keys">
        <button
          type="button"
          className="key"
          data-intent="primary"
          disabled={saving}
          onClick={() => void save()}
        >
          <span>{saving ? "Saving…" : `Save version ${next}`}</span>
        </button>
        <button type="button" className="key" data-intent="quiet" onClick={onCancel}>
          <span>Cancel</span>
        </button>
      </div>
    </section>
  );
}
