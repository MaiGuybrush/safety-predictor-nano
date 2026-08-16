from datetime import datetime, timezone

from argus_eventlog import (
    event_queue, EventStart, EventFrame, EventEnd,
    EventMeta, BboxDetection,
)

_FULL_FRAME_ROI = [[0, 0], [1, 0], [1, 1], [0, 1]]
_DEFAULT_SEVERITY = "warning"
_END_REASON = "no_longer_detected"

# (stream_key, label) -> {"event_ref": str, "absent": int}
_state = {}


def _now_iso():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _new_event_ref(label):
    return f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def process_detections(stream_key, camera_id, detections, frame_w, frame_h,
                        severity_map=None, tolerance=2):
    """把偵測結果轉成 argus-eventlog 的 EventStart/EventFrame/EventEnd，丟進 event_queue。

    detections: [{"xyxy": [x1,y1,x2,y2], "cls": int, "conf": float, "label": str}, ...]
    """
    severity_map = severity_map or {}

    by_label = {}
    for det in detections:
        by_label.setdefault(det["label"], []).append(det)

    now = _now_iso()

    for label, dets in by_label.items():
        key = (stream_key, label)
        boxes = [
            BboxDetection(
                label=label,
                x=d["xyxy"][0] / frame_w,
                y=d["xyxy"][1] / frame_h,
                w=(d["xyxy"][2] - d["xyxy"][0]) / frame_w,
                h=(d["xyxy"][3] - d["xyxy"][1]) / frame_h,
            )
            for d in dets
        ]

        if key not in _state:
            event_ref = _new_event_ref(label)
            _state[key] = {"event_ref": event_ref, "absent": 0}
            event_queue.put(EventStart(
                event_ref=event_ref,
                category=label,
                camera_id=camera_id,
                timestamp=now,
                severity=severity_map.get(label, _DEFAULT_SEVERITY),
                meta=EventMeta(roi=_FULL_FRAME_ROI),
            ))
        else:
            _state[key]["absent"] = 0

        event_queue.put(EventFrame(
            event_ref=_state[key]["event_ref"],
            camera_id=camera_id,
            timestamp=now,
            detections=boxes,
        ))

    tracked_labels = {label for (sk, label) in _state if sk == stream_key}
    for label in tracked_labels - set(by_label.keys()):
        key = (stream_key, label)
        st = _state[key]
        st["absent"] += 1
        if st["absent"] > tolerance:
            event_queue.put(EventEnd(
                event_ref=st["event_ref"],
                camera_id=camera_id,
                timestamp=now,
                reason=_END_REASON,
            ))
            del _state[key]
