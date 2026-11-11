---
name: grafana
description: Use when reading, editing, saving or migrating Grafana dashboards or panel queries through the Grafana MCP (update_dashboard, get_dashboard_by_uid, search_dashboards), when a dashboard save fails with 403, or when repointing dashboard queries to other tables or datasources.
metadata:
  review_after: "2026-12-11"
---

# grafana

Operating rules for changing Grafana dashboards through the Grafana MCP. Dashboards live in Grafana, not in git, so a bad save is only undone with Grafana's version history.

## Saving a dashboard: always pass folderUid

`update_dashboard` takes the folder as its own argument. The folder is **not** a field of the dashboard JSON you get back from `get_dashboard_by_uid`; it sits in the response metadata.

Without `folderUid`, Grafana saves the dashboard to the General (root) folder. A service account with edit rights only on a team folder then gets `403 Access denied to save dashboard`. That 403 looks like a permission problem, but it is a payload problem.

Rule: before every save, read the folder from the metadata and pass it:

```
got = get_dashboard_by_uid(uid)
dash = got.dashboard
folder = got.meta.folderUid          # e.g. the team folder's uid
update_dashboard(dashboard=dash, folderUid=folder, overwrite=true, message="...")
```

Check the returned `status` is `success` and `folderUid` is the team folder. Do not ask for a role change on a 403 until the folder is set.

## Save procedure for a migration

1. Fetch every dashboard to change with `get_dashboard_by_uid`. Keep the metadata.
2. Rewrite the targets in the JSON. Replace whole table names, longest name first, so a short name does not match inside a longer one.
3. Verify each rewritten query before saving. Grafana's query tools do not run ClickHouse or SQL, so run the SQL with the datasource's own client (for ClickHouse, a read-only user with `EXPLAIN QUERY TREE`, which checks names and types without reading data).
   - Strip `--` comments first, or a comment swallows the rest of the query.
   - Replace Grafana macros with literals: `$__fromTime`, `$__toTime`, `$__timeFilter`, `$__conditionalAll`, and `${var:sqlstring}`. A bare `IN $var` must become a list.
   - Run the original query through the same check. If the original also fails, the problem is the check, not the migration.
4. Save each dashboard with `folderUid` set.
5. Rescan. Search all dashboards (`search_dashboards` with paging, `hasMore`) and fetch each one, then grep for the old names. Expect zero hits before anything is dropped.

## Rollback

Every save creates a version. `list_dashboard_versions` shows them, and `get_dashboard_by_uid` takes an optional `version`. Restore by saving that version's JSON with the same `folderUid`.

## Checks before deleting the tables a dashboard used

- Run the rescan in step 5 again after the saves.
- Read `system.query_log` on the datasource too. A table can be quiet in logs but still feed a dashboard that is not yet rescanned, and logs only go back as far as retention allows.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| 403 `Access denied to save dashboard` after a team-folder edit grant | `folderUid` missing, so save targets General | Pass `folderUid` from `meta.folderUid` |
| 403 even with `folderUid` set | The dashboard sits in a folder the service account has no edit rights on. Dashboards in one set can live in different folders | Check `search_dashboards` for the folder title, then ask that folder's owner for Editor rights. Do not assume the team folder |
| Save succeeds but the dashboard moved | `folderUid` was wrong or omitted on an earlier save | Restore the previous version, then save with the right folder |
| Query fails only in the check | Comment or macro left in the SQL | Strip comments and macros as above, and re-run the original query |
