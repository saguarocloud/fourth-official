"use client";

import { type ReactNode, useState } from "react";

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

// In the order the form lists the choices, so ticking one off and on again changes nothing.
function toggled<T extends string>(
  names: Readonly<Record<string, string>>,
  values: readonly T[],
  value: T,
  on: boolean,
): T[] {
  const listed = (Object.keys(names) as T[]).filter((v) => (v === value ? on : values.includes(v)));
  return [...listed, ...values.filter((v) => !(v in names))];
}

interface Limit {
  readonly label: string;
  readonly min: number;
  readonly max: number;
  readonly problem: string;
}

/** The numbers a policy holds and the range the API accepts for each. */
export const LIMITS = {
  latencyBudgetMs: {
    label: "Latency budget",
    min: 1000,
    max: 30000,
    problem: "Latency budget: give a number of seconds from 1 to 30, in half seconds.",
  },
  maxItemsPerMinute: {
    label: "Items a minute",
    min: 1,
    max: 30,
    problem: "Items a minute: give a whole number from 1 to 30.",
  },
} as const satisfies Record<string, Limit>;

const LATENCY_STEP_MS = 500;

/** What is wrong with the draft's numbers, in words; empty if nothing is. */
export function problemsOf(draft: TenantPolicy): string[] {
  const step = { latencyBudgetMs: LATENCY_STEP_MS, maxItemsPerMinute: 1 } as const;
  return (Object.keys(LIMITS) as (keyof typeof LIMITS)[])
    .filter((field) => {
      const value = draft[field];
      const { min, max } = LIMITS[field];
      return !Number.isInteger(value / step[field]) || value < min || value > max;
    })
    .map((field) => LIMITS[field].problem);
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
              onChange={(event) => onChange(toggled(names, chosen, value, event.target.checked))}
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

interface TermsProps {
  readonly id: string;
  readonly label: string;
  readonly hint: string;
  readonly value: readonly string[];
  readonly onChange: (value: string[]) => void;
}

// The text is kept as typed, so a comma or a space can be typed before the next term.
function Terms({ id, label, hint, value, onChange }: TermsProps) {
  const [text, setText] = useState(() => value.join(", "));
  return (
    <Text
      id={id}
      label={label}
      hint={hint}
      value={text}
      onChange={(typed) => {
        setText(typed);
        onChange(terms(typed));
      }}
    />
  );
}

interface NumberProps {
  readonly id: string;
  readonly label: string;
  readonly hint: string;
  readonly value: number;
  readonly scale?: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly onChange: (value: number) => void;
}

// The text is kept as typed: a cleared field stays blank (and the draft holds no number) rather
// than turning into a 0 the editor never wrote.
function Whole({ id, label, hint, value, scale = 1, min, max, step, onChange }: NumberProps) {
  const [text, setText] = useState(() => String(value / scale));
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
        value={text}
        min={min}
        max={max}
        step={step}
        aria-describedby={`${id}-hint`}
        onChange={(event) => {
          const typed = event.target.value;
          setText(typed);
          onChange(typed.trim() === "" ? Number.NaN : Math.round(Number(typed) * scale));
        }}
      />
    </div>
  );
}

function Group({ legend, children }: { readonly legend: string; readonly children: ReactNode }) {
  return (
    <fieldset className="policy-group">
      <legend className="policy-group__legend">{legend}</legend>
      <div className="policy-group__fields">{children}</div>
    </fieldset>
  );
}

/** Every control of a partner's policy that the studio may change, in four groups. The API
 * checks the whole policy when it is saved and says in words what is wrong. */
export function PolicyForm({ draft, onChange }: PolicyFormProps) {
  const set = (changes: Partial<TenantPolicy>) => onChange({ ...draft, ...changes });
  return (
    <div className="policy-form">
      <Group legend="On air">
        <Text
          id="policy-name"
          label="Name on air"
          hint="As the partner's graphics name it."
          value={draft.displayName}
          onChange={(displayName) => set({ displayName })}
        />
        <Terms
          id="policy-tone"
          label="Tone"
          hint="Up to six words, separated by commas."
          value={draft.tone}
          onChange={(tone) => set({ tone: tone as TenantPolicy["tone"] })}
        />
        <Terms
          id="policy-prefer"
          label="Preferred terms"
          hint="Separated by commas."
          value={draft.preferTerms}
          onChange={(preferTerms) => set({ preferTerms })}
        />
        <Terms
          id="policy-avoid"
          label="Avoided terms"
          hint="Separated by commas. A term cannot be both preferred and avoided."
          value={draft.avoidTerms}
          onChange={(avoidTerms) => set({ avoidTerms })}
        />
      </Group>
      <Group legend="Content">
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
        <Choices
          legend="Graphics allowed"
          names={LABELS.TEMPLATES}
          chosen={draft.templates}
          locked="correction_strap"
          onChange={(templates) => set({ templates: templates as TenantPolicy["templates"] })}
        />
      </Group>
      <Group legend="Disclosure and corrections">
        <OneOf
          legend="AI disclosure"
          name="policy-disclosure"
          names={LABELS.DISCLOSURE}
          value={draft.disclosureMode}
          onChange={(disclosureMode) => set({ disclosureMode })}
        />
        <OneOf
          legend="When a correction arrives"
          name="policy-corrections"
          names={LABELS.CORRECTIONS}
          value={draft.correctionBehaviour}
          onChange={(correctionBehaviour) => set({ correctionBehaviour })}
        />
      </Group>
      <Group legend="Limits">
        <Whole
          id="policy-latency"
          label={LIMITS.latencyBudgetMs.label}
          hint="Seconds an item may take to reach air, 1 to 30."
          value={draft.latencyBudgetMs}
          scale={1000}
          min={1}
          max={30}
          step={0.5}
          onChange={(latencyBudgetMs) => set({ latencyBudgetMs })}
        />
        <Whole
          id="policy-rate"
          label={LIMITS.maxItemsPerMinute.label}
          hint="The most graphics this partner airs in any minute, 1 to 30."
          value={draft.maxItemsPerMinute}
          min={LIMITS.maxItemsPerMinute.min}
          max={LIMITS.maxItemsPerMinute.max}
          step={1}
          onChange={(maxItemsPerMinute) => set({ maxItemsPerMinute })}
        />
      </Group>
    </div>
  );
}
