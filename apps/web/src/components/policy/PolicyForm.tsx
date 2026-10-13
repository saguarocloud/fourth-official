"use client";

import type { TenantPolicy } from "@/contracts/policyHistory";
import { LABELS } from "@/domain/policy";

interface PolicyFormProps {
  readonly draft: TenantPolicy;
  readonly onChange: (draft: TenantPolicy) => void;
}

const terms = (text: string): string[] =>
  text
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

function toggled<T extends string>(values: readonly T[], value: T, on: boolean): T[] {
  return on ? [...values.filter((v) => v !== value), value] : values.filter((v) => v !== value);
}

interface ChoicesProps<T extends string> {
  readonly legend: string;
  readonly names: Readonly<Record<string, string>>;
  readonly chosen: readonly T[];
  readonly onChange: (chosen: T[]) => void;
  readonly locked?: T;
}

function Choices<T extends string>({ legend, names, chosen, onChange, locked }: ChoicesProps<T>) {
  return (
    <fieldset className="policy-field">
      <legend className="policy-field__label">{legend}</legend>
      <div className="policy-field__choices">
        {(Object.keys(names) as T[]).map((value) => (
          <label key={value} className="policy-choice">
            <input
              type="checkbox"
              checked={chosen.includes(value)}
              disabled={value === locked}
              onChange={(event) => onChange(toggled(chosen, value, event.target.checked))}
            />
            {names[value]}
            {value === locked && <span className="policy-choice__note"> (always)</span>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

interface OneOfProps<T extends string> {
  readonly legend: string;
  readonly name: string;
  readonly names: Readonly<Record<string, string>>;
  readonly value: T;
  readonly onChange: (value: T) => void;
}

function OneOf<T extends string>({ legend, name, names, value, onChange }: OneOfProps<T>) {
  return (
    <fieldset className="policy-field">
      <legend className="policy-field__label">{legend}</legend>
      <div className="policy-field__choices">
        {(Object.keys(names) as T[]).map((option) => (
          <label key={option} className="policy-choice">
            <input
              type="radio"
              name={name}
              checked={value === option}
              onChange={() => onChange(option)}
            />
            {names[option]}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

interface TextProps {
  readonly id: string;
  readonly label: string;
  readonly hint?: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
}

function Text({ id, label, hint, value, onChange }: TextProps) {
  return (
    <div className="policy-field">
      <label htmlFor={id} className="policy-field__label">
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="policy-field__hint">
          {hint}
        </p>
      )}
      <input
        id={id}
        className="policy-input"
        value={value}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

interface NumberProps {
  readonly id: string;
  readonly label: string;
  readonly hint: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly onChange: (value: number) => void;
}

function Whole({ id, label, hint, value, min, max, step, onChange }: NumberProps) {
  return (
    <div className="policy-field">
      <label htmlFor={id} className="policy-field__label">
        {label}
      </label>
      <p id={`${id}-hint`} className="policy-field__hint">
        {hint}
      </p>
      <input
        id={id}
        type="number"
        className="policy-input policy-input--number tabular"
        value={value}
        min={min}
        max={max}
        step={step}
        aria-describedby={`${id}-hint`}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

/** Every control of a partner's policy that the studio may change. The API checks the whole
 * policy when it is saved and says in words what is wrong. */
export function PolicyForm({ draft, onChange }: PolicyFormProps) {
  const set = (changes: Partial<TenantPolicy>) => onChange({ ...draft, ...changes });
  return (
    <div className="policy-form">
      <Text
        id="policy-name"
        label="Name on air"
        value={draft.displayName}
        onChange={(displayName) => set({ displayName })}
      />
      <Text
        id="policy-tone"
        label="Tone"
        hint="Up to six words, separated by commas."
        value={draft.tone.join(", ")}
        onChange={(text) => set({ tone: terms(text) as TenantPolicy["tone"] })}
      />
      <Text
        id="policy-prefer"
        label="Preferred terms"
        hint="Separated by commas."
        value={draft.preferTerms.join(", ")}
        onChange={(text) => set({ preferTerms: terms(text) })}
      />
      <Text
        id="policy-avoid"
        label="Avoided terms"
        hint="Separated by commas. A term cannot be both preferred and avoided."
        value={draft.avoidTerms.join(", ")}
        onChange={(text) => set({ avoidTerms: terms(text) })}
      />
      <Choices
        legend="Blocked topics"
        names={LABELS.TOPICS}
        chosen={draft.blockedTopics}
        onChange={(blockedTopics) => set({ blockedTopics })}
      />
      <Choices
        legend="Held for the duty editor"
        names={LABELS.KINDS}
        chosen={draft.approvalRequired}
        onChange={(approvalRequired) => set({ approvalRequired })}
      />
      <OneOf
        legend="AI disclosure"
        name="policy-disclosure"
        names={LABELS.DISCLOSURE}
        value={draft.disclosureMode}
        onChange={(disclosureMode) => set({ disclosureMode })}
      />
      <Whole
        id="policy-latency"
        label="Latency budget"
        hint="Milliseconds, 1,000 to 30,000."
        value={draft.latencyBudgetMs}
        min={1000}
        max={30000}
        step={500}
        onChange={(latencyBudgetMs) => set({ latencyBudgetMs })}
      />
      <Whole
        id="policy-rate"
        label="Items a minute"
        hint="The most graphics this partner airs in any minute, 1 to 30."
        value={draft.maxItemsPerMinute}
        min={1}
        max={30}
        step={1}
        onChange={(maxItemsPerMinute) => set({ maxItemsPerMinute })}
      />
      <Choices
        legend="Graphics allowed"
        names={LABELS.TEMPLATES}
        chosen={draft.templates}
        locked="correction_strap"
        onChange={(templates) => set({ templates: templates as TenantPolicy["templates"] })}
      />
      <OneOf
        legend="When a correction arrives"
        name="policy-corrections"
        names={LABELS.CORRECTIONS}
        value={draft.correctionBehaviour}
        onChange={(correctionBehaviour) => set({ correctionBehaviour })}
      />
    </div>
  );
}
