# On Call Runbook

Owner: Platform team
Rotation: weekly, Monday to Monday

## Escalation path

1. Primary on call is paged first through PagerDuty. Response target is 10 minutes for SEV1 and SEV2, 30 minutes for SEV3.
2. If primary does not acknowledge within the target window, secondary on call is paged automatically.
3. If both are unresponsive after 20 minutes total, the engineering manager on the escalation list is paged directly.
4. SEV1 incidents automatically notify the VP of Engineering regardless of resolution status.

## Severity definitions

- **SEV1**: full outage or data loss affecting any customer. Immediate all hands response.
- **SEV2**: significant degradation affecting multiple customers, such as delayed dashboards or elevated error rates above 5 percent.
- **SEV3**: isolated or minor issue affecting a small number of accounts, no urgent customer impact.

## Common failure scenarios

**Queue depth alert firing**: Check the transform service dashboard for batch size and worker count first. Most queue backlogs trace back to a config regression or a spike in customer data volume. See the incident postmortem archive for the April 2026 precedent.

**Auth service latency spike**: Usually tied to a Redis connection pool exhaustion. Restarting the affected pods clears it in most cases. If it recurs within an hour, escalate to the auth service owning team rather than repeating the restart.

**Warehouse query timeouts**: Check Snowflake's query history for a runaway query from a customer report. These should be killed manually and the customer's account flagged for a review of their report complexity.

## Incident commander duties

Whoever acknowledges the page first is the incident commander until they explicitly hand off. The commander opens the incident channel, posts updates at least every 30 minutes for SEV1 and SEV2, and owns writing the postmortem within 5 business days of resolution.

## Rollback procedure

Rollbacks go through the standard deploy pipeline using the previous known good version tag. Do not hotfix directly in production. If a rollback itself fails, escalate immediately rather than attempting a second rollback without review.
