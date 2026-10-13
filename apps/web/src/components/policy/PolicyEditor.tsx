"use client";

import { useState } from "react";

import type { TenantPolicy } from "@/contracts/policyHistory";
import { toYaml } from "@/domain/policy";

import { PolicyForm } from "./PolicyForm";
import { type EditBody, saveEdit } from "./usePolicyHistory";

const CONFLICT = 409;
const MAX_REASON = 200;

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
  readonly detail: string;
}

/** The partner's next version, from the form or the raw YAML, with the reason it is made. */
export function PolicyEditor({
  tenantId,
  policy,
  dutyEditor,
  onSaved,
  onCancel,
  onReload,
}: PolicyEditorProps) {
  const [view, setView] = useState<"form" | "raw">("form");
  const [draft, setDraft] = useState(policy);
  const [raw, setRaw] = useState(() => toYaml(policy));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const next = policy.version + 1;
  const ready = reason.trim().length > 0 && !saving;

  async function save() {
    setSaving(true);
    setRefusal(null);
    const edit: EditBody =
      view === "form"
        ? { policy: { ...draft }, baseVersion: policy.version, reason: reason.trim() }
        : { yaml: raw, baseVersion: policy.version, reason: reason.trim() };
    const outcome = await saveEdit(tenantId, edit);
    setSaving(false);
    if (outcome.ok) onSaved(outcome.change.version);
    else setRefusal({ status: outcome.status, detail: outcome.detail });
  }

  return (
    <section aria-labelledby="editor-heading" className="policy-editor">
      <div className="policy-editor__head">
        <h2 id="editor-heading" className="policy-editor__title">
          Version {next}
        </h2>
        <p className="policy-editor__who">
          Recorded against {dutyEditor} (demo identity). It governs the next item.
        </p>
      </div>
      <div role="tablist" aria-label="How to edit" className="policy-tabs">
        {(["form", "raw"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            id={`policy-tab-${tab}`}
            aria-selected={view === tab}
            aria-controls={`policy-panel-${tab}`}
            className="policy-tab"
            onClick={() => setView(tab)}
          >
            {tab === "form" ? "Form" : "Raw YAML"}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`policy-panel-${view}`}
        aria-labelledby={`policy-tab-${view}`}
        className="policy-panel"
      >
        {view === "form" ? (
          <PolicyForm draft={draft} onChange={setDraft} />
        ) : (
          <div className="policy-field">
            <label htmlFor="policy-raw" className="policy-field__label">
              The policy as YAML
            </label>
            <p id="policy-raw-hint" className="policy-field__hint">
              Read strictly, as a policy file is. The partner, its locale and its duty editor stay
              as they are.
            </p>
            <textarea
              id="policy-raw"
              className="policy-raw"
              value={raw}
              spellCheck={false}
              rows={18}
              aria-describedby="policy-raw-hint"
              onChange={(event) => setRaw(event.target.value)}
            />
          </div>
        )}
      </div>
      <div className="policy-field">
        <label htmlFor="policy-reason" className="policy-field__label">
          Why
        </label>
        <input
          id="policy-reason"
          className="policy-input"
          value={reason}
          maxLength={MAX_REASON}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
      {refusal && (
        <div role="alert" className="policy-refusal">
          <p>{refusal.detail}</p>
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
          disabled={!ready}
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
