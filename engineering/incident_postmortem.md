# Incident Postmortem: Dashboard Data Delay, April 2026

Severity: SEV2
Duration: 3 hours 40 minutes
Author: Incident commander, Platform team

## Summary

Between 2:14 PM and 5:54 PM Central on April 9, dashboard data for 34 enterprise customers was delayed by up to 2 hours. No data was lost. The root cause was a queue backlog in the transform service triggered by a misconfigured batch size after a routine deploy.

## Timeline

- 2:14 PM: Deploy of transform service version 4.12.0 completes
- 2:20 PM: Batch size config accidentally reverted to a value from an old staging environment, 10x smaller than production setting
- 2:35 PM: Queue depth alert fires in the on call channel, acknowledged within 4 minutes
- 3:10 PM: Root cause identified as the batch size regression
- 3:45 PM: Rollback to version 4.11.2 begins
- 4:20 PM: Rollback completes, queue begins draining
- 5:54 PM: Queue depth returns to normal, incident resolved

## Root cause

The batch size parameter was stored in an environment specific config file that was not properly separated between staging and production during a recent config management migration. The deploy pulled the staging value instead of the production value.

## Impact

34 enterprise accounts saw dashboard data delayed by 45 minutes to 2 hours. 3 customers filed support tickets. No SLA breaches occurred, as the affected accounts have a 4 hour freshness SLA.

## What went well

The queue depth alert fired within 6 minutes of the regression, well inside the target detection window. Rollback was executed cleanly with no data loss.

## What went poorly

The config separation issue had been flagged in a code review comment 3 weeks earlier and was not addressed before merge. Detection to root cause took 50 minutes, longer than the 20 minute target for this alert class.

## Action items

- Separate staging and production config into fully isolated files, owner: Platform team, due April 23
- Add an automated check that blocks deploy if batch size config differs more than 5x from the prior production value, owner: Platform team, due May 7
- Revisit the review comment triage process so flagged concerns are tracked to resolution, owner: Engineering manager, due April 30
