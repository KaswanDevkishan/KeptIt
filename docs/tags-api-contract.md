# Tags API Contract

## Contract rules

All routes are under `/api/v1`, require the existing opaque session cookie, and apply the existing
trusted-origin protection to mutations. Authentication establishes identity; every query is
authorized with the current User's ID before joins, filters, counts, sorting, or pagination.
Private responses use `Cache-Control: no-store`.

Strict request schemas reject unknown fields. The API never returns `user_id`, `normalized_name`,
database constraint/trigger details, or another User's existence. A valid absent UUID and another
User's UUID return the same `404 resource_not_found` status, code, message, and body shape.

## Endpoints

| Method and path | Purpose | Success |
| --- | --- | --- |
| `GET /tags` | Search/list the caller's Tags | `200` |
| `POST /tags` | Create a Tag | `201` |
| `GET /tags/{tag_id}` | Read one owned Tag | `200` |
| `PATCH /tags/{tag_id}` | Rename one owned Tag | `200` |
| `DELETE /tags/{tag_id}` | Permanently delete a Tag | `204` |
| `PUT /tags/{tag_id}/discoveries/{discovery_id}` | Idempotently attach a Tag | `201` or `200` |
| `DELETE /tags/{tag_id}/discoveries/{discovery_id}` | Remove an attachment | `204` |
| `GET /tags/{tag_id}/discoveries` | List assigned Discoveries | `200` |

Tag-oriented membership routes deliberately mirror Spaces. There is no bulk or Discovery-oriented
membership mutation route in MVP.

## Representations

### Tag

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "name": "Python",
  "discovery_count": 12,
  "created_at": "2026-08-05T12:00:00Z",
  "updated_at": "2026-08-05T12:00:00Z"
}
```

`discovery_count` includes active and archived owned Discoveries. It is never affected by current
list filters. Timestamps are RFC 3339 UTC instants.

### Compact Tag summary

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "name": "Python"
}
```

### Tag membership

```json
{
  "id": "0e984725-c51c-4bf4-9960-e1c80e27aba0",
  "tag_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "discovery_id": "b8d42b2a-b68c-4d0e-a2aa-40f17a74a1a2",
  "created_at": "2026-08-05T12:30:00Z"
}
```

Ownership and normalized comparison values are never exposed.

## Create a Tag

`POST /api/v1/tags`

Request:

```json
{
  "name": " Python "
}
```

Success: `201 Created`, a Tag representation, and
`Location: /api/v1/tags/{tag_id}`. The returned display name is trimmed (`Python`).

Errors include `401`, `415`, `422 validation_error`, `409 tag_name_conflict`, `429`, and generic
`500`. A limit breach uses `422 tag_limit_reached` rather than revealing internal counts. Create
never accepts ownership, ID, normalized name, color, or timestamps.

## List and search Tags

`GET /api/v1/tags?limit=50&cursor=opaque&q=py&sort=name_asc`

Parameters:

| Parameter | Contract |
| --- | --- |
| `limit` | integer; default 50; minimum 1; maximum 100 |
| `cursor` | optional opaque integrity-protected cursor for the effective sort |
| `q` | optional; trim; 1–50 Unicode code points; NFKC/case-folded substring match |
| `sort` | `name_asc` (default) or `updated_desc` |

Response:

```json
{
  "items": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "name": "Python",
      "discovery_count": 12,
      "created_at": "2026-08-05T12:00:00Z",
      "updated_at": "2026-08-05T12:00:00Z"
    }
  ],
  "next_cursor": null
}
```

`name_asc` orders by stored normalized name then ID. `updated_desc` orders by `updated_at DESC,
id DESC`. Search applies before ordering/pagination and only within the owner. An empty result is
`200` with an empty array. Invalid/stale/tampered cursors are `422`, never a silent first page.

## Read and rename a Tag

`GET /api/v1/tags/{tag_id}` returns `200` with the Tag or safe `404`.

`PATCH /api/v1/tags/{tag_id}` request:

```json
{
  "name": "python"
}
```

The body must contain exactly `name`; `null` is invalid. Success returns `200` with the current Tag.
Renaming only display casing is allowed for the same Tag. A byte-for-byte no-op returns `200` and
does not change `updated_at`. A normalized conflict with another owned Tag returns
`409 tag_name_conflict`; the transaction changes nothing.

## Delete a Tag

`DELETE /api/v1/tags/{tag_id}` has no body. Success is `204 No Content`. It permanently deletes the
Tag and cascades assignments only. No Discovery is deleted, archived, or otherwise changed.
Repeating the delete or using a foreign/absent valid UUID returns safe `404`. The UI confirmation is
mandatory product behavior but is not represented by an easily spoofed request boolean.

## Attach and remove a Tag

`PUT /api/v1/tags/{tag_id}/discoveries/{discovery_id}` has no body.

- First successful attachment returns `201 Created`, the membership representation, and a
  membership `Location` if the application exposes one.
- An existing exact assignment returns `200 OK` with the existing representation and unchanged
  `created_at`.
- Both parents are loaded under the current owner in the same transaction. A foreign or absent Tag,
  foreign or absent Discovery, or indistinguishable mixed-owner pair returns the same `404`.
- A 20-Tags-per-Discovery limit breach returns `422 discovery_tag_limit_reached`; retries of an
  existing pair remain idempotent and do not fail the cap.

`DELETE /api/v1/tags/{tag_id}/discoveries/{discovery_id}` returns `204` only when an owned
membership was removed. An absent pair, absent parent, or foreign resource returns the same `404`.
Archived Discoveries may be attached and detached exactly like active Discoveries.

## List Discoveries for a Tag

`GET /api/v1/tags/{tag_id}/discoveries` returns the existing paginated public Discovery list shape.
It first verifies the owned Tag, then applies the membership and all owner predicates.

Supported parameters reuse the Discovery list contract:

- `limit` and opaque cursor;
- `archive=active|archived|all` (default `active`);
- optional platform, favourite, Space, and keyword criteria already supported by the library;
- existing stable Discovery sort/order.

The endpoint does not accept a second Tag filter. A Tag with no matches returns `200` with empty
items. Archived assignments remain counted and appear when archive filtering permits them.

Example:

```json
{
  "items": [
    {
      "id": "b8d42b2a-b68c-4d0e-a2aa-40f17a74a1a2",
      "original_url": "https://example.test/article",
      "platform": "generic_web",
      "custom_title": "Typed validation patterns",
      "tags": [
        {
          "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
          "name": "Python"
        }
      ]
    }
  ],
  "next_cursor": null
}
```

The omitted Discovery fields remain exactly as defined by the existing contract.

## Discovery response integration

Every Discovery list/search/card and detail response adds `tags`, always an array:

```json
"tags": [
  {"id": "...", "name": "Python"},
  {"id": "...", "name": "read-later"}
]
```

An untagged Discovery returns `"tags": []`. Summaries are ordered by normalized name then Tag ID,
but normalized values are not returned. At most 20 summaries exist under the MVP cap. The backend
loads them in a bounded aggregate/batch, not through per-Discovery queries.

Discovery create and patch request bodies do not gain Tag IDs in MVP. The frontend saves/updates
the Discovery through its existing contract, then performs explicit idempotent membership calls.
This prevents Tag failure from rolling back a core Discovery save and preserves API compatibility.

## Library filtering

The existing `GET /api/v1/discoveries` gains optional `tag_id=<uuid>`. It supports one Tag only.
The server first resolves the Tag with `(current_user.id, tag_id)` and returns safe `404` if absent
or foreign; malformed UUID syntax is `422`. A matching Tag is joined through `discovery_tags`.

The predicate is:

```text
owner AND archive AND tag AND optional Space AND optional platform
      AND optional favourite AND optional keyword
```

Existing filter defaults, sorting, cursor stability, and Discovery representation remain unchanged.
The cursor binds the effective Tag/filter set so reuse with different criteria is invalid.

## Normalization and conflicts

The server trims outer Unicode whitespace, rejects null/control characters and an empty result,
enforces 1–50 display code points, stores the trimmed display value, and computes the private
comparison key using Unicode NFKC followed by default case folding. Internal whitespace is not
collapsed.

For one User, `Python`, `python`, `Ｐｙｔｈｏｎ`, and ` python ` conflict. Different Users may use the
same normalized name. The API never exposes the normalized form. Concurrent create/rename
conflicts are mapped from the named database constraint to the same `409` as a pre-detected
conflict; database messages are never returned.

## Error format and status codes

Errors use the existing envelope:

```json
{
  "error": {
    "code": "tag_name_conflict",
    "message": "You already have a Tag with that name.",
    "request_id": "req_opaque",
    "details": {
      "field": "name"
    }
  }
}
```

Allowed Tag-specific public codes are `tag_name_conflict`, `tag_limit_reached`, and
`discovery_tag_limit_reached`. General codes include `resource_not_found`, `validation_error`,
`unsupported_media_type`, `rate_limit_exceeded`, and `internal_error`. Details may name invalid
fields but never echo unsafe input, normalized values, owners, names of existing foreign resources,
database objects, or membership state.

| Status | Meaning |
| --- | --- |
| `200` | Read/list/update or existing idempotent attachment |
| `201` | Tag or membership created |
| `204` | Tag/membership deleted |
| `401` | No valid session |
| `404` | Valid resource/pair absent or not owned |
| `409` | Normalized Tag name conflict |
| `415` | Body content type is not JSON where JSON is required |
| `422` | Invalid path/query/body or configured Tag cap |
| `429` | Per-user/IP abuse limit; bounded `Retry-After` when known |
| `500` | Generic unexpected failure with request ID |

## Trusted origin, limits, and privacy

POST, PATCH, PUT, and DELETE require the same trusted `Origin`/CSRF policy as existing cookie-based
mutations. Non-browser clients do not bypass authentication, ownership, validation, or rate limits.
Production applies per-user and IP-aware limits to Tag and membership writes. Tag names and search
text are private user data and are excluded from logs, metrics labels, audit detail, exception
reports, and AI-provider input.
