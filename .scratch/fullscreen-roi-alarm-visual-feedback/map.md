# Fullscreen ROI Alarm Visual Feedback Map

## Decisions so far
- Client-side Ray-Casting algorithm for point-in-polygon evaluation in `drawCanvas()` (ADR-010, ADR-012 compliant).
- Dynamic styling for bounding boxes inside ROI: red border (`#ff3333`), 3px stroke, `[ALARM]` label, dashed if stale.
- Dynamic styling for ROI polygon: translucent red fill (`rgba(255, 51, 51, 0.25)`), red border, `[ ROI: <NAME> - INTRUSION ]` tag.
- Dynamic CSS alert for fullscreen modal: `box-shadow` pulse glow and `[ ZONE: ALARM TRIGGERED ]` badge.

## Tickets
- [01-fullscreen-roi-alarm-visual-feedback.md](issues/01-fullscreen-roi-alarm-visual-feedback.md) (Status: resolved)
- [02-tests-and-user-manual.md](issues/02-tests-and-user-manual.md) (Status: resolved, Blocked by: 01)
