import os
import queue
import threading
import time
import cv2
import numpy as np
from datetime import datetime, timezone

import argus_eventlog
from argus_eventlog import (
    event_queue, EventStart, EventFrame, EventEnd,
    EventMeta, BboxDetection,
)

_FULL_FRAME_ROI = [[0, 0], [1, 0], [1, 1], [0, 1]]
_DEFAULT_SEVERITY = "warning"
_END_REASON = "no_longer_detected"

# (stream_key, label) -> {"event_ref": str, "absent": int, "snapshotted": bool}
_state = {}

# Asynchronous Snapshot Worker Queue & Thread
_snapshot_queue = queue.Queue()
_snapshot_worker_thread = None
_snapshot_worker_lock = threading.Lock()


def _snapshot_worker():
    while True:
        try:
            item = _snapshot_queue.get()
            if item is None:
                _snapshot_queue.task_done()
                break
            file_path, frame = item
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                cv2.imwrite(file_path, frame)
            except Exception:
                pass
            finally:
                _snapshot_queue.task_done()
        except Exception:
            pass


def _ensure_snapshot_worker():
    global _snapshot_worker_thread
    with _snapshot_worker_lock:
        if _snapshot_worker_thread is None or not _snapshot_worker_thread.is_alive():
            _snapshot_worker_thread = threading.Thread(
                target=_snapshot_worker,
                name="SnapshotWorkerThread",
                daemon=True
            )
            _snapshot_worker_thread.start()


def enqueue_snapshot(file_path, frame):
    _ensure_snapshot_worker()
    _snapshot_queue.put((file_path, frame))


def _get_base_dir():
    import sys
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.normpath(os.path.join(exe_dir, 'recordings'))


MIN_VALID_EPOCH_PTS = 946684800.0  # 2000-01-01 00:00:00 UTC


def _format_timestamp(pts=None):
    """將 PTS (秒) 轉換為 ISO 8601 UTC 毫秒字串 (YYYY-MM-DDTHH:MM:SS.mmmZ)。
    若 pts 為無效、<= 0 或非絕對 Unix Epoch (例如串流相對秒數 < 946684800) 則 fallback 至系統時間。
    """
    if pts is not None and isinstance(pts, (int, float)) and pts >= MIN_VALID_EPOCH_PTS:
        dt = datetime.fromtimestamp(pts, tz=timezone.utc)
    else:
        dt = datetime.now(tz=timezone.utc)
    return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}.{dt.microsecond // 1000:03d}Z"


def _now_iso(pts=None):
    return _format_timestamp(pts)


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
                        severity_map=None, tolerance=2, zone=None, pts=None,
                        clean_frame=None, base_dir=None):
    """把偵測結果轉成 argus-eventlog 的 EventStart/EventFrame/EventEnd，丟進 event_queue。

    detections: [{"xyxy": [x1,y1,x2,y2], "cls": int, "conf": float, "label": str}, ...]
    zone: optional dict {"polygon": [[x1, y1], ...], "zone_name": str, "trigger_mode": str, "sensitivity": float}
    pts: optional float PTS (秒)
    clean_frame: optional ndarray 未繪製標註框之原始影像
    base_dir: optional str recordings 基礎輸出目錄
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

    now = _format_timestamp(pts)
    pts_val = float(pts) if (pts is not None and isinstance(pts, (int, float)) and pts >= MIN_VALID_EPOCH_PTS) else time.time()

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
            snap_rel_path = f"snapshots/{pts_val:.3f}_{event_ref}.jpg"
            if clean_frame is not None:
                base = base_dir or _get_base_dir()
                full_snap_path = os.path.join(base, camera_id, "snapshots", f"{pts_val:.3f}_{event_ref}.jpg")
                enqueue_snapshot(full_snap_path, clean_frame.copy())
                meta = EventMeta(roi=roi, zone_name=zone_name, snapshot_path=snap_rel_path)
            else:
                meta = EventMeta(roi=roi, zone_name=zone_name)

            _state[key] = {"event_ref": event_ref, "absent": 0, "snapshotted": True}
            event_queue.put(EventStart(
                event_ref=event_ref,
                category=label,
                camera_id=camera_id,
                timestamp=now,
                severity=severity_map.get(label, _DEFAULT_SEVERITY),
                meta=meta,
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
