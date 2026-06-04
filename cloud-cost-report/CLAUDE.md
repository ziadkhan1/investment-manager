# cloud-cost-report — T-SQL

## What this is
T-SQL query work to build a **cloud cost report**.

> ⚠️ Scaffold — fill in the specifics below as they're decided. Anything marked
> _(TBD)_ is a placeholder, not a fact.

## Target platform _(TBD)_
- Engine: _(TBD — e.g. Azure Synapse Serverless SQL, Synapse Dedicated SQL Pool,
  Microsoft Fabric Warehouse, or SQL Server)_
- Note: the `qbo/` task already lands data in Synapse/Fabric Delta tables, so this
  report may read from the same lakehouse/warehouse.

## Source data _(TBD)_
- Table(s) / view(s): _(TBD)_
- Grain (one row per …): _(TBD)_
- Key columns: _(TBD)_

## Report requirements _(TBD)_
- What the report should show (dimensions, measures, time grain): _(TBD)_
- Filters / date range: _(TBD)_
- Output target (view, stored proc, ad-hoc query, scheduled): _(TBD)_

## Conventions
- Keep `.sql` files in this folder.
- Prefer set-based T-SQL; comment non-obvious CTEs.
- Match the engine's dialect (Serverless vs Dedicated vs Fabric differ on a few
  features — e.g. `OPENROWSET`, identity, `CREATE TABLE AS`).
