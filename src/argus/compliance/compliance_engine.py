"""compliance_engine.py - 人員裝備防護 (PPE) 與條件式工安合規規則引擎

提供：
1. 目標類別標準化 (Class Normalization)
2. 空間包含度 (Loose Box Containment) 與 IoU 幾何計算
3. PPE 雙模關聯比對 (Dual-mode: direct_negative & head_anchor)
4. 宣告式工安複合條件矩陣評估 (Declarative Compliance Rules Evaluation)
"""

from typing import List, Dict, Any, Tuple, Optional, Set


DEFAULT_PPE_MAPPING: Dict[str, str] = {
    "person": "person",
    "head": "head",
    "helmet": "helmet",
    "no_helmet": "no_helmet",
    "vest": "vest",
    "no_vest": "no_vest",
    "cone": "cone",
    "guardrail": "guardrail",
}


def box_area(box: List[float]) -> float:
    """計算邊界框面積 [x1, y1, x2, y2]。"""
    if not box or len(box) < 4:
        return 0.0
    w = max(0.0, float(box[2]) - float(box[0]))
    h = max(0.0, float(box[3]) - float(box[1]))
    return w * h


def box_intersection(box_a: List[float], box_b: List[float]) -> float:
    """計算兩個邊界框的重疊面積。"""
    if not box_a or len(box_a) < 4 or not box_b or len(box_b) < 4:
        return 0.0
    ix1 = max(float(box_a[0]), float(box_b[0]))
    iy1 = max(float(box_a[1]), float(box_b[1]))
    ix2 = min(float(box_a[2]), float(box_b[2]))
    iy2 = min(float(box_a[3]), float(box_b[3]))
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    return iw * ih


def box_containment(inner_box: List[float], outer_box: List[float]) -> float:
    """計算 inner_box 被 outer_box 包含的面積比例 (Area(inner ∩ outer) / Area(inner))。"""
    iarea = box_area(inner_box)
    if iarea <= 0.0:
        return 0.0
    inter = box_intersection(inner_box, outer_box)
    return inter / iarea


def box_iou(box_a: List[float], box_b: List[float]) -> float:
    """計算兩個邊界框的 IoU (Intersection over Union)。"""
    inter = box_intersection(box_a, box_b)
    if inter <= 0.0:
        return 0.0
    area_a = box_area(box_a)
    area_b = box_area(box_b)
    union = area_a + area_b - inter
    if union <= 0.0:
        return 0.0
    return inter / union


def box_center(box: List[float]) -> Tuple[float, float]:
    """計算邊界框中心座標 (cx, cy)。"""
    if not box or len(box) < 4:
        return (0.0, 0.0)
    return ((float(box[0]) + float(box[2])) / 2.0, (float(box[1]) + float(box[3])) / 2.0)


def is_point_in_box(pt: Tuple[float, float], box: List[float]) -> bool:
    """判斷座標點是否落在邊界框內。"""
    if not box or len(box) < 4:
        return False
    return float(box[0]) <= pt[0] <= float(box[2]) and float(box[1]) <= pt[1] <= float(box[3])


class ComplianceEngine:
    """工安合規與 PPE 規則引擎。"""

    def __init__(self, ppe_class_mapping: Optional[Dict[str, str]] = None):
        self.mapping = dict(DEFAULT_PPE_MAPPING)
        if isinstance(ppe_class_mapping, dict):
            self.mapping.update(ppe_class_mapping)

    def set_mapping(self, ppe_class_mapping: Dict[str, str]):
        """動態更新類別映射表。"""
        self.mapping = dict(DEFAULT_PPE_MAPPING)
        if isinstance(ppe_class_mapping, dict):
            self.mapping.update(ppe_class_mapping)

    def normalize_label(self, raw_label: str) -> str:
        """根據映射表將原始類別字串標準化為內部標準名稱。"""
        if not raw_label:
            return ""
        return self.mapping.get(str(raw_label), str(raw_label))

    def associate_ppe_for_person(
        self,
        person_det: Dict[str, Any],
        associated_dets: List[Dict[str, Any]],
        strategy: str = "direct_negative",
        required_ppe: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, bool], List[str]]:
        """針對單一人員偵測物件執行 PPE 關聯分析。

        回傳:
        - ppe_status: {"helmet": bool, "vest": bool}
        - violations: list of violation strings (如 "missing_helmet", "missing_vest")
        """
        required = set(required_ppe or ["helmet", "vest"])
        person_box = person_det.get("xyxy", [])

        # 分類內部相關物件
        heads = []
        helmets = []
        no_helmets = []
        vests = []
        no_vests = []

        for d in associated_dets:
            lbl = self.normalize_label(d.get("label", ""))
            if lbl == "head":
                heads.append(d)
            elif lbl == "helmet":
                helmets.append(d)
            elif lbl == "no_helmet":
                no_helmets.append(d)
            elif lbl == "vest":
                vests.append(d)
            elif lbl == "no_vest":
                no_vests.append(d)

        ppe_status = {"helmet": True, "vest": True}
        violations = []

        # 1. 安全帽判定
        if strategy == "head_anchor":
            if heads:
                # 偵測到頭部：檢查頭部是否戴安全帽或存在未戴安全帽標籤
                head_has_helmet = False
                for h in heads:
                    h_box = h.get("xyxy", [])
                    # 檢查是否有 no_helmet 與 head 重疊
                    for nh in no_helmets:
                        if box_iou(h_box, nh.get("xyxy", [])) >= 0.15 or box_containment(nh.get("xyxy", []), h_box) >= 0.3:
                            head_has_helmet = False
                            break
                    # 檢查是否有 helmet 與 head 重疊
                    for hm in helmets:
                        hm_box = hm.get("xyxy", [])
                        if box_iou(h_box, hm_box) >= 0.15 or box_containment(hm_box, h_box) >= 0.25 or box_containment(h_box, hm_box) >= 0.25:
                            head_has_helmet = True
                            break
                    if not head_has_helmet and helmets:
                        # 寬鬆包含判定：若 helmet 位於 person 上半部且靠近頭部
                        for hm in helmets:
                            if box_containment(hm.get("xyxy", []), person_box) >= 0.4:
                                head_has_helmet = True
                                break
                if not head_has_helmet:
                    ppe_status["helmet"] = False
                    if "helmet" in required:
                        violations.append("missing_helmet")
                else:
                    ppe_status["helmet"] = True
            else:
                # 未明確偵測到獨立 head（例如遮擋、背對或彎腰）：依賴直接標籤
                if no_helmets:
                    ppe_status["helmet"] = False
                    if "helmet" in required:
                        violations.append("missing_helmet")
                elif helmets:
                    ppe_status["helmet"] = True
                else:
                    # 無任何頭部/安全帽訊號，避免彎腰時誤報，若在 required 中則標記未檢出
                    if "helmet" in required and person_det.get("in_zone", False):
                        ppe_status["helmet"] = False
                        violations.append("missing_helmet")
                    else:
                        ppe_status["helmet"] = True
        else:
            # direct_negative 策略
            if no_helmets:
                ppe_status["helmet"] = False
                if "helmet" in required:
                    violations.append("missing_helmet")
            elif helmets:
                ppe_status["helmet"] = True
            else:
                if "helmet" in required and person_det.get("in_zone", False):
                    ppe_status["helmet"] = False
                    violations.append("missing_helmet")
                else:
                    ppe_status["helmet"] = True

        # 2. 反光背心判定
        if no_vests:
            ppe_status["vest"] = False
            if "vest" in required:
                violations.append("missing_vest")
        elif vests:
            ppe_status["vest"] = True
        else:
            if "vest" in required and person_det.get("in_zone", False):
                ppe_status["vest"] = False
                violations.append("missing_vest")
            else:
                ppe_status["vest"] = True

        return ppe_status, violations

    def evaluate_rules(
        self,
        active_zone_name: str,
        external_states: Dict[str, Any],
        zone_detections: List[Dict[str, Any]],
        all_detections: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """評估宣告式工安條件規則矩陣。

        回傳:
        - rule_events: 產生的違規事件清單
        - missing_barriers: 缺失的阻隔物名稱清單
        """
        rule_events = []
        missing_barriers = []

        if not rules:
            return rule_events, missing_barriers

        ext_states = external_states or {}

        # 提取區域內與全畫面的標準標籤集合
        zone_labels = {self.normalize_label(d.get("label", "")) for d in zone_detections}
        all_labels = {self.normalize_label(d.get("label", "")) for d in all_detections}

        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("enabled", True):
                continue

            when = rule.get("when", {})
            if not isinstance(when, dict):
                continue

            # 1. 條件比對: external_state
            when_ext = when.get("external_state")
            if isinstance(when_ext, dict):
                mismatch = False
                for src_key, exp_val in when_ext.items():
                    curr_val = ext_states.get(src_key)
                    if str(curr_val).upper() != str(exp_val).upper():
                        mismatch = True
                        break
                if mismatch:
                    continue

            # 2. 條件比對: zone
            when_zone = when.get("zone")
            if when_zone and active_zone_name:
                if str(when_zone).strip().lower() != str(active_zone_name).strip().lower():
                    continue

            # 3. 條件比對: detected
            when_detected = when.get("detected")
            if when_detected:
                if isinstance(when_detected, str):
                    when_detected = [when_detected]
                if isinstance(when_detected, list):
                    # 需在區域內偵測到指定物件
                    req_norm = {self.normalize_label(x) for x in when_detected}
                    if not req_norm.issubset(zone_labels):
                        continue

            # when 條件全部滿足，進行需求檢查 (require_any, require_all, require_ppe)
            on_violation = rule.get("on_violation", {})
            severity = on_violation.get("severity", "HIGH")
            category = on_violation.get("category", "safety_rule_violation")

            # A. require_any (例如: cone 或 guardrail 至少需有一項)
            require_any = rule.get("require_any")
            if require_any and isinstance(require_any, list):
                any_norm = [self.normalize_label(x) for x in require_any]
                if not any(lbl in all_labels for lbl in any_norm):
                    missing_barriers.extend(any_norm)
                    rule_events.append({
                        "rule_id": rule.get("id", "unnamed_rule"),
                        "rule_name": rule.get("name", rule.get("id", "")),
                        "severity": severity,
                        "category": category,
                        "missing_items": any_norm,
                        "reason": f"未依規定設置安全阻隔物（需至少包含: {', '.join(any_norm)}）",
                    })

            # B. require_all
            require_all = rule.get("require_all")
            if require_all and isinstance(require_all, list):
                all_norm = [self.normalize_label(x) for x in require_all]
                missing = [lbl for lbl in all_norm if lbl not in all_labels]
                if missing:
                    rule_events.append({
                        "rule_id": rule.get("id", "unnamed_rule"),
                        "rule_name": rule.get("name", rule.get("id", "")),
                        "severity": severity,
                        "category": category,
                        "missing_items": missing,
                        "reason": f"未齊全安全防護項目（缺少: {', '.join(missing)}）",
                    })

            # C. require_ppe
            require_ppe = rule.get("require_ppe")
            if require_ppe and isinstance(require_ppe, list):
                ppe_norm = [self.normalize_label(x) for x in require_ppe]
                # 檢查區域內所有人員
                for p_det in zone_detections:
                    if self.normalize_label(p_det.get("label", "")) == "person":
                        p_ppe = p_det.get("ppe", {})
                        p_viols = p_det.get("violations", [])
                        for item in ppe_norm:
                            if not p_ppe.get(item, True) or f"missing_{item}" in p_viols:
                                rule_events.append({
                                    "rule_id": rule.get("id", "unnamed_rule"),
                                    "rule_name": rule.get("name", rule.get("id", "")),
                                    "severity": severity,
                                    "category": f"missing_{item}",
                                    "missing_items": [item],
                                    "reason": f"現場人員未穿戴必要安全裝備 ({item})",
                                })

        return rule_events, missing_barriers

    def evaluate(
        self,
        detections: List[Dict[str, Any]],
        stream_zone: Optional[Dict[str, Any]] = None,
        external_states: Optional[Dict[str, Any]] = None,
        rules: Optional[List[Dict[str, Any]]] = None,
        ppe_class_mapping: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """執行全流程合規評估。

        參數:
        - detections: 原始/扁平化偵測清單 (每項包含 xyxy, label, conf, in_zone)
        - stream_zone: 當前串流之 Zone 設定字典
        - external_states: 外部設備狀態字典 (如 {"stocker_01": "MAINTENANCE"})
        - rules: 工安條件規則矩陣
        - ppe_class_mapping: 自訂類別映射字典

        回傳:
        - enriched_detections: 附加 ppe, violations, is_compliant 欄位之偵測清單
        - compliance_events: 需拋出的工安違規事件清單
        - compliance_summary: 供 UI 與 API 呈現之總覽字典
        """
        if ppe_class_mapping:
            self.set_mapping(ppe_class_mapping)

        zone_cfg = stream_zone or {}
        active_zone_name = zone_cfg.get("zone_name", "")
        strategy = zone_cfg.get("ppe_strategy", "direct_negative")
        required_ppe = zone_cfg.get("required_ppe", ["helmet", "vest"])

        # 1. 類別標準化與分類
        normalized_dets = []
        persons = []
        non_persons = []

        for det in detections:
            d = dict(det)
            norm_lbl = self.normalize_label(d.get("label", ""))
            d["normalized_label"] = norm_lbl
            normalized_dets.append(d)
            if norm_lbl == "person":
                persons.append(d)
            else:
                non_persons.append(d)

        # 2. 人員 PPE 關聯比對
        for p in persons:
            p_box = p.get("xyxy", [])
            # 尋找與該人員關聯之物件 (包含度 >= 0.4 或 中心點在 person 框內)
            associated = []
            for obj in non_persons:
                obj_box = obj.get("xyxy", [])
                cnt = box_containment(obj_box, p_box)
                center = box_center(obj_box)
                if cnt >= 0.4 or is_point_in_box(center, p_box):
                    associated.append(obj)

            ppe_status, violations = self.associate_ppe_for_person(
                p, associated, strategy=strategy, required_ppe=required_ppe
            )
            p["ppe"] = ppe_status
            p["violations"] = violations
            p["is_compliant"] = (len(violations) == 0)

        # 3. 複合工安規則評估
        zone_dets = [d for d in normalized_dets if d.get("in_zone", False)]
        rule_events, missing_barriers = self.evaluate_rules(
            active_zone_name=active_zone_name,
            external_states=external_states or {},
            zone_detections=zone_dets,
            all_detections=normalized_dets,
            rules=rules or [],
        )

        # 4. 匯總違規與狀態
        all_violations = []
        for p in persons:
            if p.get("in_zone", False) and p.get("violations"):
                all_violations.extend(p["violations"])
        for r_evt in rule_events:
            all_violations.append(r_evt.get("category", "violation"))

        has_person_in_zone = any(p.get("in_zone", False) for p in persons)
        if all_violations or rule_events:
            status = "VIOLATION"
        elif has_person_in_zone:
            status = "COMPLIANT"
        else:
            status = "NORMAL"

        compliance_summary = {
            "status": status,
            "violations": sorted(list(set(all_violations))),
            "missing_barriers": sorted(list(set(missing_barriers))),
            "external_state": external_states or {},
            "rule_events": rule_events,
            "active_zone": active_zone_name,
        }

        return normalized_dets, rule_events, compliance_summary
