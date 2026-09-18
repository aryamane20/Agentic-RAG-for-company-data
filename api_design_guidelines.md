# API Design Guidelines

Owner: Platform team
Applies to: all internal and customer facing services

## Naming and structure

Endpoints are plural nouns, resource based, and versioned in the path. Use `/v1/accounts/{account_id}/dashboards`, not `/getDashboards` or `/v1/dashboard`.

Query parameters use snake case. Path parameters are always the resource's primary identifier, never a secondary lookup field like email or slug.

## Response shape

Every response body wraps data in a `data` key. Errors follow a consistent shape:

```
{
  "error": {
    "code": "invalid_request",
    "message": "account_id is required",
    "request_id": "req_8f2a1c"
  }
}
```

The `request_id` is required on every error response and should be logged on the service side so support and engineering can trace a specific failure.

## Pagination

All list endpoints are cursor paginated, not offset paginated. Offset pagination caused duplicate and skipped rows under concurrent writes during the 2025 Q4 incident with the accounts list endpoint, so it is no longer permitted for new endpoints.

## Authentication

Internal service to service calls use short lived JWTs issued by the auth service, valid for 5 minutes. Customer facing endpoints use long lived API keys, scoped per account, rotatable through the settings page.

Never accept a permission scope directly in a request payload. Scopes are resolved server side from the token, never trusted from client input.

## Rate limits

Customer facing endpoints are rate limited to 100 requests per minute per API key by default, configurable per contract for enterprise accounts. Internal services are not rate limited but should implement backoff on retry.

## Deprecation policy

A deprecated endpoint stays live for 6 months minimum after a replacement ships, with deprecation headers on every response during that window. Breaking changes without a new version number are not permitted under any circumstance.

## Review process

Any new external facing endpoint requires sign off from the platform team lead before merge. Internal only endpoints can be merged with standard code review.
