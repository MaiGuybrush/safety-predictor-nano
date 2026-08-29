# Effort Map: PTS 時間戳同步、事件單次截圖與資料保留機制

## Notes
- Feature branch/effort for importing NVR and detection sync guide Section 4.
- Spec: `docs/prd/pts_time_sync_and_event_snapshot_prd.md` / `.scratch/pts-time-sync-and-event-snapshot/spec.md`.

## Decisions-so-far
- Timestamps in `recordings/{camera_id}/events/` JSONL converted from frame PTS to ISO 8601 UTC milliseconds (`YYYY-MM-DDTHH:MM:SS.mmmZ`).
- Snapshot storage path: `recordings/{camera_id}/snapshots/{pts:.3f}_{event_ref}.jpg`.
- Single clean snapshot per event, non-blocking via background queue worker.
- Retention cleanup configured via `event_retention_days` (default 30), executed daily via daemon thread.

## Fog / Open Issues
- None.

## Tickets Frontier
- `01-pts-time-sync.md` (unblocked)
- `03-retention-cleaner.md` (unblocked)
