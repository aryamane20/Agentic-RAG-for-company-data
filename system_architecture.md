# System Architecture Overview

Owner: Platform team
Last reviewed: March 2026

## High level shape

Solstice's product, Pulseboard, is built as a set of services behind a single API gateway. The main services are:

- **Ingest service**: receives customer event data over HTTPS and Kafka, validates schema, writes to a staging table in Postgres
- **Transform service**: reads from staging on a 5 minute cadence, applies customer defined transformation rules, writes to the warehouse
- **Warehouse**: Snowflake, partitioned by customer account, retained for 24 months by default
- **Query service**: serves dashboard queries against the warehouse, backed by a Redis cache layer with a 10 minute TTL
- **Auth service**: handles login, session tokens, and role based permissions for both customer users and internal staff

## Data flow

Customer data enters through the ingest service, which is the only service allowed to write to staging. This is intentional. Early in the company's history, multiple services wrote to staging directly, which caused a data corruption incident in 2024 that took 3 days to fully reconcile. Ingest now owns that write path exclusively.

## Infrastructure

Everything runs on AWS, primarily in us east 1 with a us west 2 failover region for the warehouse and auth service only. Compute runs on EKS. Deploys go through a standard CI pipeline in GitHub Actions, with staging and production environments gated by manual approval for production.

## Scaling notes

The transform service is the current bottleneck under load. At peak, transform jobs for large enterprise accounts can take up to 40 minutes to complete, which delays dashboard freshness for those customers. A rewrite to move transform logic onto a stream processing model using Flink is planned for Q3 2026.

## On call ownership

Each service has a named owning team, listed in the internal service catalog. Cross service incidents default to the ingest team as first responder, since most cascading failures originate there.

## Security boundaries

The auth service is the only service with direct database credentials for the permissions tables. All other services validate access through short lived tokens issued by auth, scoped to a single customer account and a single operation.
