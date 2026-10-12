import { ShieldAlert, ShieldCheck, ShieldX, type LucideIcon } from "lucide-react";
import { useId } from "react";

import type { ProvenanceRecord as Record, SignedProvenance } from "@/contracts/provenance";
import { PARTNERS } from "@/domain/broadcast";
import {
  lifeOf,
  type ProvenanceAnswer,
  type SealTone,
  sealOf,
  signerOf,
} from "@/domain/provenance";
import { type ItemState, StatusLamp } from "@/components/ui/StatusLamp";

// The record's states, in the shared lamp vocabulary: a rejected item was dropped.
const LAMP: Readonly<{ [S in Record["state"]]: ItemState }> = {
  on_air: "on_air",
  pending_approval: "pending_approval",
  rejected: "dropped",
  retracted: "retracted",
  amended: "amended",
};

const SEAL_ICONS: Readonly<{ [T in SealTone]: LucideIcon }> = {
  verified: ShieldCheck,
  development: ShieldAlert,
  failed: ShieldX,
};

function partnerName(tenantId: string): string {
  return PARTNERS.find((p) => p.id === tenantId)?.name ?? tenantId;
}

function Seal({ answer }: { readonly answer: ProvenanceAnswer }) {
  const seal = sealOf(answer);
  const signed = answer.provenance;
  const Icon = SEAL_ICONS[seal.tone];
  return (
    <section aria-label="Verification" className="seal" data-tone={seal.tone}>
      <Icon aria-hidden="true" className="seal__icon" strokeWidth={1.5} />
      <div className="seal__text">
        <p className="seal__title">{seal.title}</p>
        {seal.detail && <p className="seal__detail">{seal.detail}</p>}
        {signed && (
          <p className="seal__by">
            {signerOf(signed)} · Issued by {signed.record.issuer}, signed at{" "}
            <time dateTime={signed.record.issuedAt}>
              {signed.record.issuedAt.slice(11, 19)} UTC
            </time>
          </p>
        )}
      </div>
    </section>
  );
}

function Claims({ record }: { readonly record: Record }) {
  return (
    <ol aria-label="Claims" className="claims">
      {record.claims.map((claim, index) => (
        <li key={index} className="claim">
          <p lang={record.locale} className="claim__text">
            {claim.text}
          </p>
          <p className="claim__note">
            Rests on {claim.evidence.eventIds.length === 1 ? "event" : "events"}{" "}
            <span className="claim__ids">{claim.evidence.eventIds.join(", ")}</span>
            {claim.evidence.metricSnapshotIds.length > 0 && (
              <>
                {" "}
                and stats{" "}
                <span className="claim__ids">{claim.evidence.metricSnapshotIds.join(", ")}</span>
              </>
            )}
          </p>
        </li>
      ))}
    </ol>
  );
}

function Life({ record }: { readonly record: Record }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="record__life">
      <h3 id={heading} className="panel-heading">
        Its life
      </h3>
      <ol aria-labelledby={heading} className="life">
        {lifeOf(record).map((step) => (
          <li key={step.label} className="life__step" data-tone={step.tone}>
            <span aria-hidden="true" className="life__mark" />
            <h4 className="life__label">{step.label}</h4>
            <p className="life__detail">{step.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function Facts({ signed }: { readonly signed: SignedProvenance }) {
  const { record } = signed;
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="record__facts">
      <h3 id={heading} className="panel-heading">
        The record
      </h3>
      <dl className="facts">
        <dt>Item</dt>
        <dd className="facts__id">{record.itemId}</dd>
        <dt>Match</dt>
        <dd>
          {record.matchId} · Feed entry {record.feedEntry}
        </dd>
        <dt>Key</dt>
        <dd className="facts__id">{signed.keyId}</dd>
        <dt>Content hash (SHA-256)</dt>
        <dd className="facts__id">{signed.contentHash}</dd>
        <dt>Signature ({signed.algorithm})</dt>
        <dd className="facts__id">{signed.signature}</dd>
      </dl>
    </section>
  );
}

/** An item's signed record, read as the item annotated: its words large, each claim's evidence in
 * the margin, the seal above and its life beneath. Shared by Provenance and the public Verify page. */
export function ProvenanceRecord({ answer }: { readonly answer: ProvenanceAnswer }) {
  const signed = answer.provenance;
  return (
    <article id="record" className="record" aria-label="Provenance record" tabIndex={-1}>
      <Seal answer={answer} />
      {signed && (
        <>
          <header className="record__head">
            <span className="record__partner">{partnerName(signed.record.tenantId)}</span>
            <span className="record__locale">{signed.record.locale}</span>
            <span className="record__version">Version {signed.record.version}, as signed</span>
            <StatusLamp state={LAMP[signed.record.state]} />
            {signed.record.disclosure?.label && (
              <span lang={signed.record.locale} className="record__label">
                {signed.record.disclosure.label}
              </span>
            )}
          </header>
          <h2 lang={signed.record.locale} className="record__headline">
            {signed.record.headline}
          </h2>
          <Claims record={signed.record} />
          <div className="record__below">
            <Life record={signed.record} />
            <Facts signed={signed} />
          </div>
        </>
      )}
    </article>
  );
}
