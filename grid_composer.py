import cv2
import numpy as np

def annotate_frame(frame, detections, stream_label=""):
    """
    對原始影像繪製 YOLO 偵測框與類別標籤，並在左上角疊加串流來源標籤。
    """
    display_frame = frame.copy()
    
    # 繪製 Bounding Box
    for det in detections:
        xyxy = det.get("xyxy", [])
        if isinstance(xyxy, list) and len(xyxy) > 0 and isinstance(xyxy[0], (list, tuple)):
            coords = xyxy[0]
        else:
            coords = xyxy
        x1, y1, x2, y2 = map(int, coords)
        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label_str = f"Class {det['cls']} ({det['conf']:.2f})"
        cv2.putText(display_frame, label_str, (x1, max(y1 - 10, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 左上角疊加串流來源標籤
    if stream_label:
        cv2.putText(display_frame, stream_label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 65), 2, cv2.LINE_AA)

    return display_frame

def compose_grid(frames, target_width=640):
    """
    將多路影像幀合成 Grid（最多 2 欄）：
    - 1 路：退化為單路顯示，寬度為 target_width
    - 2+ 路：2 欄排列，單格寬度 target_width // 2，不足格位以純黑填補
    """
    if not frames:
        return None
    
    if len(frames) == 1:
        frame = frames[0]
        h, w = frame.shape[:2]
        if w != target_width:
            target_h = int(h * target_width / w)
            return cv2.resize(frame, (target_width, target_h))
        return frame

    cols = 2
    rows = (len(frames) + cols - 1) // cols
    cell_w = target_width // cols
    
    # 計算 cell 高度
    sample_h, sample_w = frames[0].shape[:2]
    cell_h = int(sample_h * cell_w / sample_w)
    
    resized_frames = [cv2.resize(f, (cell_w, cell_h)) for f in frames]
    
    # 不足格位補純黑
    total_slots = rows * cols
    black_cell = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
    while len(resized_frames) < total_slots:
        resized_frames.append(black_cell.copy())
        
    row_imgs = []
    for r in range(rows):
        row_frames = resized_frames[r * cols : (r + 1) * cols]
        row_img = np.hstack(row_frames)
        row_imgs.append(row_img)
        
    grid_img = np.vstack(row_imgs)
    return grid_img
