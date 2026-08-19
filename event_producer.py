import cv2
import numpy as np
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


def _clip_polygon(subject_polygon, clip_line):
    """Sutherland-Hodgman clipping against one half-plane:
    clip_line is ('left', val) | ('right', val) | ('top', val) | ('bottom', val)
    """
    side, val = clip_line
    output_list = []
    if not subject_polygon:
        return output_list

    def is_inside(p):
        if side == 'left': return p[0] >= val
        if side == 'right': return p[0] <= val
        if side == 'top': return p[1] >= val
        if side == 'bottom': return p[1] <= val
        return True

    def intersection(p1, p2):
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        if side in ('left', 'right'):
            if abs(x2 - x1) < 1e-9:
                return [val, y1]
            t = (val - x1) / (x2 - x1)
            return [val, y1 + t * (y2 - y1)]
        else:
            if abs(y2 - y1) < 1e-9:
                return [x1, val]
            t = (val - y1) / (y2 - y1)
            return [x1 + t * (x2 - x1), val]

    s = subject_polygon[-1]
    for e in subject_polygon:
        if is_inside(e):
            if is_inside(s):
                output_list.append(e)
            else:
                output_list.append(intersection(s, e))
                output_list.append(e)
        elif is_inside(s):
            output_list.append(intersection(s, e))
        s = e
    return output_list


def _polygon_area(poly):
    if len(poly) < 3:
        return 0.0
    area = 0.0
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1]
        area -= poly[j][0] * poly[i][1]
    return abs(area) / 2.0


def _is_inside_zone(det, polygon, frame_w, frame_h, trigger_mode="center", sensitivity=0.0):
    if not polygon or len(polygon) < 3 or frame_w <= 0 or frame_h <= 0:
        return True

    xyxy = det.get("xyxy", [0, 0, 0, 0])
    bx1 = xyxy[0] / float(frame_w)
    by1 = xyxy[1] / float(frame_h)
    bx2 = xyxy[2] / float(frame_w)
    by2 = xyxy[3] / float(frame_h)

    if trigger_mode == "intersect":
        clipped = polygon
        clipped = _clip_polygon(clipped, ('left', bx1))
        clipped = _clip_polygon(clipped, ('right', bx2))
        clipped = _clip_polygon(clipped, ('top', by1))
        clipped = _clip_polygon(clipped, ('bottom', by2))

        inter_area = _polygon_area(clipped)
        bbox_area = max(1e-9, (bx2 - bx1) * (by2 - by1))
        overlap_ratio = inter_area / bbox_area

        if sensitivity <= 0.0:
            if inter_area > 1e-9:
                return True
            pts = np.array(polygon, dtype=np.float32)
            for pt in [[bx1, by1], [bx2, by1], [bx2, by2], [bx1, by2]]:
                if cv2.pointPolygonTest(pts, (float(pt[0]), float(pt[1])), False) >= 0:
                    return True
            cx = (bx1 + bx2) / 2.0
            cy = (by1 + by2) / 2.0
            return cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0
        else:
            return overlap_ratio >= float(sensitivity)

    cx = (bx1 + bx2) / 2.0
    cy = (by1 + by2) / 2.0
    pts = np.array(polygon, dtype=np.float32)
    return cv2.pointPolygonTest(pts, (float(cx), float(cy)), False) >= 0


def process_detections(stream_key, camera_id, detections, frame_w, frame_h,
                        severity_map=None, tolerance=2, zone=None):
    """把偵測結果轉成 argus-eventlog 的 EventStart/EventFrame/EventEnd，丟進 event_queue。

    detections: [{"xyxy": [x1,y1,x2,y2], "cls": int, "conf": float, "label": str}, ...]
    zone: optional dict {"polygon": [[x1, y1], ...], "zone_name": str, "trigger_mode": str, "sensitivity": float}
    """
    severity_map = severity_map or {}

    roi = _FULL_FRAME_ROI
    zone_name = None

    if isinstance(zone, dict) and zone.get("polygon") and len(zone["polygon"]) >= 3:
        polygon = zone["polygon"]
        roi = polygon
        zone_name = zone.get("zone_name")
        trigger_mode = zone.get("trigger_mode", "center")
        sensitivity = float(zone.get("sensitivity", 0.0))
        detections = [
            d for d in detections 
            if (d["in_zone"] if "in_zone" in d else _is_inside_zone(d, polygon, frame_w, frame_h, trigger_mode=trigger_mode, sensitivity=sensitivity))
        ]

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
                meta=EventMeta(roi=roi, zone_name=zone_name),
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
