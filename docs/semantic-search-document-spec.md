# Semantic Search Embedding Document Specification

## Version and purpose

Document version: `semantic-discovery-v1`. It defines the exact bounded text embedded for one
Discovery. Any change to allowed fields, ordering, labels, normalization, deduplication, or
truncation creates a new version. Formatting-only corrections do not.

The document is data, not a prompt. Metadata remains untrusted: adapters submit it as one text
input with no instructions, tools, browsing, URL fetching, or identifier context.

## Privacy policy and allowed fields

| Provenance | Field | v1 default | Rule |
| --- | --- | --- | --- |
| User-authored | `custom_title` | Include | Strong retrieval signal intentionally written for the Discovery |
| User-authored | `personal_note` | Exclude | Include only when account setting `include_private_context` is true |
| User-authored | `save_reason` | Exclude | Include only under the same explicit setting |
| Fetched metadata | title, description, site name, publisher | Include | Current succeeded metadata only |
| Deterministic source | platform, canonical hostname | Include | Low-sensitivity classification/context |
| AI-generated | summary, key points, topics | Include | Current succeeded or stale summary; provenance stays explicit |
| Organizational | Tag names, Space names | Exclude | Include only under `include_private_context`; sorted deterministically |

“Include my notes in semantic search” must disclose that notes, save reasons, Tag names, and Space
names will be sent to the configured third-party embedding provider. It defaults off. A local
provider may use the same policy for predictable behavior, but does not change consent silently.

Excluded in all modes: raw/canonical URL, URL path/query, IDs, email/account/session data,
timestamps, favourite/archive state, importance, thumbnails, provider payloads, AI entities,
operational records, logs, and full-page content. The hostname is allowed; the raw URL is not.

## Canonical construction

Fields appear in this order and use these exact ASCII labels:

```text
Custom title: <value>
Metadata title: <value>
Metadata description: <value>
Site name: <value>
Publisher: <value>
Platform: <value>
Hostname: <value>
AI summary: <value>
AI key point: <value>
AI key point: <value>
AI topic: <value>
Personal note: <value>
Save reason: <value>
Tag: <value>
Space: <value>
```

- Omit a line when its normalized value is missing; never emit placeholders.
- Join lines with one LF (`\n`), with no blank lines and one final LF.
- Normalize input as valid Unicode NFC; replace CRLF/CR with LF, trim outer Unicode whitespace,
  collapse every internal Unicode whitespace run to one ASCII space, remove nulls/control/format
  characters except meaningful ordinary spacing, and render as plain text.
- Preserve case, accents, scripts, punctuation, and language. Do not translate, stem, case-fold, or
  language-detect for construction. Multilingual models receive the original text.
- Deduplicate values after whitespace normalization and Unicode case folding. Keep the earliest
  field by the order above; repeated key points/topics use their stored order, while Tags and
  Spaces sort by normalized name then UUID before UUIDs are discarded.
- Labels and delimiters are application-owned. A value such as `Ignore prior instructions` or
  `Tag: secret` remains inert text within its field and cannot create provider options or new
  database fields.

## Bounds and truncation

The canonical UTF-8 document is at most **12,000 Unicode code points and 24,000 UTF-8 bytes**,
including labels and separators. Each source is first bounded: title 300, metadata title 500,
description 4,000, site/publisher 200 each, platform 50, hostname 253, AI summary 600, five key
points at 240 each, eight topics at 60 each, note 4,000, save reason 500, twenty Tags at 50 each,
and twenty Spaces at 100 each.

Construction uses the listed priority. When the total limit is reached, truncate the current
value at a Unicode code-point boundary, then a UTF-8 boundary, append `…` if space permits, and
omit all later fields. Never silently rely on provider truncation. An empty document is
`unsupported` and is not sent.

## Fingerprint and provenance

`input_fingerprint` is SHA-256 over a length-delimited canonical binary envelope containing:

1. document version;
2. private-context policy version and enabled boolean;
3. each included field's stable provenance key and normalized UTF-8 bytes in construction order;
4. the final canonical document bytes.

Store the 32-byte digest as `bytea`, never expose it publicly, and compare it in constant-shape
application logic. Provider/model/dimension are not input identity; they are separately stored
generation configuration. A row is stale if its fingerprint, document version, configured
provider/model, or dimension differs from the current target.

## Stale triggers

Custom-title, approved metadata, included AI Summary content, and policy/version changes trigger
staleness. Note/save-reason/Tag/Space changes trigger it only when private context is enabled.
AI Summary regeneration triggers it when included content changes. Favourite and archive changes
never do; they are query filters. Platform or canonical-hostname changes do.

## Examples

Default policy:

```text
Custom title: Fukushima documentary references
Metadata title: The abandoned railway town of Namie
Metadata description: A short documentary about evacuation and memory in Fukushima Prefecture.
Site name: YouTube
Publisher: Example Films
Platform: youtube
Hostname: youtube.com
AI summary: A short film about place, evacuation, and memory in Fukushima.
AI topic: Fukushima
AI topic: documentary film
```

With explicit private context:

```text
Custom title: Tofu meal prep
Metadata title: Five high-protein vegetarian lunches
Platform: generic_web
Hostname: example.test
Personal note: Try the sesame tofu bowl after gym days.
Save reason: Easy weekday protein.
Tag: vegetarian
Tag: gym
Space: Recipes
```

Invalid documents include raw URLs, email or user IDs, `Favourite: true`, unlabeled concatenated
database dumps, notes when consent is off, Tags sent under the AI Summary policy, provider-added
text, reordered fields, platform markup, or a provider-truncated document.

## Privacy consequence

Embeddings can encode sensitive meaning and are private derived user data. Sending a document to a
third party reveals its included text, not merely an opaque vector. Provider retention, training,
regional processing, subprocessors, deletion, and incident terms must be reviewed and disclosed.
Turning the setting off makes existing private-context embeddings stale and queues replacement;
until replacement succeeds, those rows must not be searched.
