# Project Read API

This is the calling contract for the project detail and project list endpoints.
Interactive OpenAPI documentation is also available at `/docs` outside production.

## Authentication and authorization

Both endpoints require the HTTP-only `access_token` cookie issued by login or
onboarding and the effective `projects.view` permission.

- Clients can read only their organization's projects.
- RIV3R users can read projects from every organization.
- Agency and resource users cannot use these endpoints.
- Read requests do not create audit events.

```http
Cookie: access_token=<signed-access-jwt>
```

## Get one project

```http
GET /api/projects/{project_id}
```

| Path parameter | Type | Required | Meaning |
| --- | --- | --- | --- |
| `project_id` | UUID | Yes | Project identifier to retrieve. |

Only active records are returned. A client receives `404` for a missing,
soft-deleted, or foreign-organization project, preventing disclosure of foreign
IDs. RIV3R can retrieve any non-deleted project.

```bash
curl --cookie "access_token=$ACCESS_TOKEN" \
  "https://api.example.com/api/projects/6fdcf080-90c8-4b88-8f27-02a392be9898"
```

Successful response (`200`):

```json
{
  "id": "6fdcf080-90c8-4b88-8f27-02a392be9898",
  "created_at": "2026-10-04T08:30:00Z",
  "updated_at": "2026-10-04T08:30:00Z",
  "deleted_at": null,
  "org_id": "45ccff08-2ee5-4bb6-abd1-a8b5c8f14140",
  "created_by_user_id": "d79269ad-3036-4521-8a64-81d8294bedaa",
  "spoc_user_id": "a12a3ab7-fbd3-4219-b22f-453de2b40e71",
  "title": "API modernization",
  "description": "Modernize the customer API",
  "status": "draft",
  "deadline_date": "2026-12-31",
  "budget": "12500.00",
  "currency": "USD",
  "published_at": null,
  "domain": "Software",
  "skill_tags": ["python", "fastapi"]
}
```

Embedding vectors and embedding metadata are never returned.

## List projects

```http
GET /api/projects
```

### Query parameters

| Name | Type | Default | Matching and validation |
| --- | --- | --- | --- |
| `page` | integer | `1` | One-based; minimum `1`. |
| `page_size` | integer | `20` | Between `1` and `100`. |
| `org_id` | UUID | none | Exact match; RIV3R-only. Clients receive `403` whenever supplied. A nonexistent RIV3R target returns `404`. |
| `spoc_user_id` | UUID | none | Exact SPOC identifier match. |
| `status` | enum | none | Exact `draft`, `published`, `closed`, or `cancelled` match. |
| `title` | string | none | Case-insensitive substring after trimming. |
| `description` | string | none | Case-insensitive substring after trimming. |
| `domain` | string | none | Case-insensitive substring after trimming. |
| `skill_tags` | repeated string | none | Every tag must exist; values are trimmed, lowercased, and de-duplicated. Empty tags are invalid. |
| `sort_by` | enum | `created_at` | `created_at`, `deadline_date`, or `published_at`. |
| `sort_order` | enum | `desc` | `asc` or `desc`. |

Every supplied filter is combined with `AND`. `org_id`, `spoc_user_id`, and
`status` are typed exact-match parameters and are not text-search fields. Repeat
`skill_tags` to require multiple tags:

```text
?skill_tags=python&skill_tags=fastapi
```

When sorting by `published_at`, unpublished projects always appear last. Project
ID is an automatic secondary sort key, making pagination deterministic.

```bash
curl --get --cookie "access_token=$ACCESS_TOKEN" \
  --data-urlencode "org_id=45ccff08-2ee5-4bb6-abd1-a8b5c8f14140" \
  --data-urlencode "status=published" \
  --data-urlencode "title=platform" \
  --data-urlencode "skill_tags=Python" \
  --data-urlencode "skill_tags=FastAPI" \
  --data-urlencode "sort_by=published_at" \
  --data-urlencode "sort_order=desc" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20" \
  "https://api.example.com/api/projects"
```

Successful response (`200`):

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

Every item uses the detail response schema. A page beyond the last page returns
`200` with an empty `items` array and preserves `total` and `total_pages`.

## Errors

Known errors contain `message` and `detail` fields.

| Status | Cause |
| --- | --- |
| `400` | Invalid UUID, enum, page bounds, sort option, blank text filter, blank skill tag, or other validation failure. |
| `401` | Missing, invalid, expired, or revoked access cookie. |
| `403` | Disallowed organization type, missing `projects.view`, or client-supplied `org_id`. |
| `404` | Missing/deleted detail project, concealed foreign client project, or nonexistent RIV3R organization target. |
| `500` | Unexpected server/storage failure; internal details are not exposed. |

## Caching and freshness

Successful detail and list reads are cached for `CACHE_TTL`. Creation invalidates
the affected organization's lists and global RIV3R lists. Publishing additionally
invalidates the project detail. Redis failures do not fail reads or mutations; if
invalidation fails, cached data can remain stale until the TTL expires.
