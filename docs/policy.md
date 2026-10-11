# Partner policies

Each broadcast partner has one policy: a versioned YAML file in `services/policy/src/fourth_official_policy/policies/`, named for the partner and reviewed in pull requests like code. The contract is `TenantPolicy` (`packages/contracts`, `tenant-policy.schema.json`).

| Partner | Locale | Disclosure | A named editor decides on | Corrections |
|---|---|---|---|---|
| Northlight Sport | en-GB | `label-unless-approved` | recaps | auto-amend |
| Tribuna Austral | es-MX | `label-all` | insights and recaps | retract and notify |
| Rheinblick Sport | de-DE | `eu-strict` | recaps | auto-amend |

## Loading

`FilePolicyStore` loads every `<partner>.yaml` once, strictly:
- YAML is parsed with `safe_load`, so tags cannot construct objects;
- files over 64 KB are refused;
- unknown fields, wrong types and incoherent combinations are refused;
- a file must be named for the partner it describes.

An invalid file stops the service with a message naming the file and each problem, rather than letting a partner run on a half-understood policy. Every loaded policy keeps the SHA-256 of its file, so each published item can record exactly what applied.

The contract itself refuses:
- a locale other than the partner's;
- a policy without the correction strap (every partner shows corrections);
- a policy that routes an item kind for approval without allowing its graphic;
- a term both preferred and avoided (compared after Unicode normalisation).

## Disclosure

`disclose(policy, item_kind, approval)` picks the label from a table, in the partner's language. A model never writes it.

| | Not reviewed | Approved by an editor |
|---|---|---|
| `label-all`, `eu-strict` | AI-generated / Generado con IA / KI-generiert | AI-assisted · Reviewed by {editor} (and in es, de) |
| `label-unless-approved` | AI-generated | no label |

Data (stats, the score, corrections) is not written by agents and carries no AI label. A rejection is not a review.

## Approval routing

`approval_required(policy, item_kind)` is true only for narrative items (insights, recaps) that the policy routes to an editor. Data never waits: a correction held for approval would leave a wrong fact on air. Until the Approvals slice lands, routed items stay `pending_approval`, off air.

## Blocked topics

`blocked_topics_in(text, policy)` is the first, deterministic screen for topics a partner never covers. The topics are injury speculation, betting, transfer rumours, criticism of referees, and off-field matters. Each language has its own word lists:
- Every term matches as a whole word or phrase, after folding case and accents. "Lesion" is caught as well as "lesión".
- German compound words are listed one by one, not matched as stems. A stem inside a word would catch ordinary football, such as "betrug" in "Der Ballbesitz betrug…" or "wette" in "Wetter".
- Words with an everyday football meaning appear only in unambiguous phrases, or not at all:
  - "robo de balón" is winning the ball, and "resultado parcial" is the half-time score;
  - "against the odds" is not betting;
  - "Regelverletzung" is a foul, not an injury.

The tests pin both directions: the cases each language must catch, and the everyday sentences it must leave alone. It errs on refusing: an item that touches a blocked topic falls back to a template.

## Loading safeguards

The policy directory must hold exactly one `<partner>.yaml` for each partner, and nothing else. The store refuses all of the following, each with a message naming the file and, for YAML errors, the line:
- a missing partner, an empty directory, or a file with another extension;
- symlinks, files over 64 KB (checked before reading), and text that is not UTF-8;
- repeated keys, which would silently drop a rule;
- YAML aliases.
