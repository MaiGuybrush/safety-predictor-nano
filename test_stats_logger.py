import os
import shutil
import tempfile
import unittest
import logging
from logging.handlers import TimedRotatingFileHandler

from stats_logger import StatsLogger


class TestStatsLogger(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.perf_log = os.path.join(self.test_dir, "logs", "test_perf.log")
        self.det_log = os.path.join(self.test_dir, "logs", "test_det.log")

    def tearDown(self):
        # Close any handlers before removing directory
        perf_logger = logging.getLogger("performance")
        for h in list(perf_logger.handlers):
            h.close()
            perf_logger.removeHandler(h)
            
        det_logger = logging.getLogger("detection")
        for h in list(det_logger.handlers):
            h.close()
            det_logger.removeHandler(h)

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auto_create_log_directory(self):
        """測試日誌目錄不存在時能自動遞迴建立目錄"""
        nested_perf = os.path.join(self.test_dir, "sub1", "sub2", "perf.log")
        nested_det = os.path.join(self.test_dir, "sub1", "sub2", "det.log")
        self.assertFalse(os.path.exists(os.path.dirname(nested_perf)))

        logger = StatsLogger(log_file=nested_perf, detection_log_file=nested_det, backup_count=3)
        self.assertTrue(os.path.exists(os.path.dirname(nested_perf)))

    def test_timed_rotating_handler_configuration(self):
        """測試日誌處理器為 TimedRotatingFileHandler 且參數設定正確"""
        logger = StatsLogger(log_file=self.perf_log, detection_log_file=self.det_log, backup_count=5)
        
        self.assertEqual(len(logger.perf_logger.handlers), 1)
        self.assertEqual(len(logger.det_logger.handlers), 1)
        
        perf_handler = logger.perf_logger.handlers[0]
        det_handler = logger.det_logger.handlers[0]
        
        self.assertIsInstance(perf_handler, TimedRotatingFileHandler)
        self.assertIsInstance(det_handler, TimedRotatingFileHandler)
        
        self.assertEqual(perf_handler.when, "MIDNIGHT")
        self.assertEqual(perf_handler.backupCount, 5)
        self.assertEqual(perf_handler.encoding, "utf-8")
        
        self.assertEqual(det_handler.when, "MIDNIGHT")
        self.assertEqual(det_handler.backupCount, 5)
        self.assertEqual(det_handler.encoding, "utf-8")

    def test_log_stats_and_detections_utf8(self):
        """測試效能日誌與偵測日誌能正確以 UTF-8 寫入中文與多語系串流名稱"""
        logger = StatsLogger(log_file=self.perf_log, detection_log_file=self.det_log, backup_count=3)
        
        logger.add_inference_time(15.5)
        logger.add_inference_time(20.5)
        logger.log_stats()
        
        detections = [
            {"cls": 0, "conf": 0.95, "xyxy": [[10, 20, 100, 200]], "label": "person"}
        ]
        logger.log_detection("rtsp://127.0.0.1/大門入口", detections)
        
        # Flush handlers
        for h in logger.perf_logger.handlers:
            h.flush()
        for h in logger.det_logger.handlers:
            h.flush()

        self.assertTrue(os.path.exists(self.perf_log))
        self.assertTrue(os.path.exists(self.det_log))

        with open(self.perf_log, "r", encoding="utf-8") as f:
            perf_content = f.read()
        self.assertIn("Avg Inference: 18.00ms", perf_content)
        self.assertIn("Max Inference: 20.50ms", perf_content)

        with open(self.det_log, "r", encoding="utf-8") as f:
            det_content = f.read()
        self.assertIn("rtsp://127.0.0.1/大門入口", det_content)
        self.assertIn("Class:0, Conf:0.95", det_content)

    def test_reinitialization_handler_cleanup_no_duplicate_logs(self):
        """測試動態重新初始化 Logger 時，舊 Handler 能被清理，不會產生重複日誌輸出"""
        logger1 = StatsLogger(log_file=self.perf_log, detection_log_file=self.det_log, backup_count=3)
        logger2 = StatsLogger(log_file=self.perf_log, detection_log_file=self.det_log, backup_count=3)

        self.assertEqual(len(logger2.perf_logger.handlers), 1)
        self.assertEqual(len(logger2.det_logger.handlers), 1)

        logger2.add_inference_time(10.0)
        logger2.log_stats()

        for h in logger2.perf_logger.handlers:
            h.flush()

        with open(self.perf_log, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        # 應該只有一行，而不是因為多個 handler 輸出兩行
        self.assertEqual(len(lines), 1)

    def test_rollover_backup_retention(self):
        """測試手動觸發輪轉時保留歷史檔案數量不超過 backupCount"""
        backup_count = 2
        logger = StatsLogger(log_file=self.perf_log, detection_log_file=self.det_log, backup_count=backup_count)
        perf_handler = logger.perf_logger.handlers[0]

        # 寫入初始日誌並輪轉 4 次
        for i in range(4):
            logger.add_inference_time(10.0 + i)
            logger.log_stats()
            perf_handler.flush()
            perf_handler.doRollover()

        # 檢查 logs 目錄下 perf 相關檔案數量
        log_dir = os.path.dirname(self.perf_log)
        perf_files = [f for f in os.listdir(log_dir) if "test_perf.log" in f]
        # 主檔案 + 最多 backup_count 個歷史檔案 = 最多 3 個
        self.assertLessEqual(len(perf_files), backup_count + 1)


if __name__ == "__main__":
    unittest.main()
