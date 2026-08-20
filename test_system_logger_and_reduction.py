import io
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import shutil
import sys
import tempfile
import unittest
import yaml

from config_manager import ConfigManager
from stats_logger import SystemLogger, setup_system_logger, get_system_logger, configure_werkzeug_logger


class TestSystemLoggerAndReduction(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.system_log = os.path.join(self.test_dir, "logs", "test_system.log")

    def tearDown(self):
        # Cleanup handlers on system logger
        sys_logger = logging.getLogger("system")
        for h in list(sys_logger.handlers):
            try:
                h.close()
            except Exception:
                pass
            sys_logger.removeHandler(h)

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_system_logger_creation_and_handlers(self):
        """驗證 SystemLogger 建立雙軌處理器 (Console StreamHandler 與 TimedRotatingFileHandler)"""
        logger_wrapper = SystemLogger(
            log_file=self.system_log,
            log_level="INFO",
            backup_count=5,
            name="system"
        )
        logger = logger_wrapper.get_logger()

        self.assertEqual(len(logger.handlers), 2)
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, TimedRotatingFileHandler)]
        file_handlers = [h for h in logger.handlers if isinstance(h, TimedRotatingFileHandler)]

        self.assertEqual(len(stream_handlers), 1)
        self.assertEqual(len(file_handlers), 1)

        file_h = file_handlers[0]
        self.assertEqual(file_h.when, "MIDNIGHT")
        self.assertEqual(file_h.backupCount, 5)
        self.assertEqual(file_h.encoding, "utf-8")
        self.assertEqual(file_h.level, logging.INFO)

        console_h = stream_handlers[0]
        self.assertEqual(console_h.stream, sys.stdout)
        self.assertEqual(console_h.level, logging.INFO)

    def test_system_logger_dual_output(self):
        """驗證訊息同時寫入檔案並輸出至 stdout"""
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            logger_wrapper = SystemLogger(
                log_file=self.system_log,
                log_level="INFO",
                backup_count=3,
                name="system"
            )
            logger_wrapper.info("Test system info message 測試雙軌日誌")

            for h in logger_wrapper.get_logger().handlers:
                h.flush()

            stdout_output = sys.stdout.getvalue()
            self.assertIn("Test system info message 測試雙軌日誌", stdout_output)
            self.assertIn("[INFO]", stdout_output)
            self.assertIn("[system]", stdout_output)

            self.assertTrue(os.path.exists(self.system_log))
            with open(self.system_log, "r", encoding="utf-8") as f:
                file_content = f.read()
            self.assertIn("Test system info message 測試雙軌日誌", file_content)
            self.assertIn("[INFO]", file_content)
            self.assertIn("[system]", file_content)
        finally:
            sys.stdout = old_stdout

    def test_system_logger_log_level_filtering(self):
        """驗證日誌等級抑制效果 (例如 WARNING 等級時 DEBUG/INFO 不寫入)"""
        logger_wrapper = SystemLogger(
            log_file=self.system_log,
            log_level="WARNING",
            backup_count=3,
            name="system"
        )
        logger_wrapper.debug("Debug should be filtered")
        logger_wrapper.info("Info should be filtered")
        logger_wrapper.warning("Warning should be recorded")
        logger_wrapper.error("Error should be recorded")

        for h in logger_wrapper.get_logger().handlers:
            h.flush()

        with open(self.system_log, "r", encoding="utf-8") as f:
            file_content = f.read()

        self.assertNotIn("Debug should be filtered", file_content)
        self.assertNotIn("Info should be filtered", file_content)
        self.assertIn("Warning should be recorded", file_content)
        self.assertIn("Error should be recorded", file_content)

    def test_setup_system_logger_singleton_and_cleanup(self):
        """驗證 setup_system_logger 函式能取得 logger 且多次呼叫不會重複新增 handlers"""
        logger1 = setup_system_logger(
            log_file=self.system_log,
            log_level="INFO",
            backup_count=3,
            name="system"
        )
        logger2 = setup_system_logger(
            log_file=self.system_log,
            log_level="INFO",
            backup_count=3,
            name="system"
        )

        inner_logger = get_system_logger("system")
        self.assertEqual(len(inner_logger.handlers), 2)

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            logger2.info("Single line test")
            for h in inner_logger.handlers:
                h.flush()
            with open(self.system_log, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            self.assertEqual(len(lines), 1)
        finally:
            sys.stdout = old_stdout

    def test_configure_werkzeug_logger(self):
        """驗證 Werkzeug Logger 等級設為 WARNING"""
        configure_werkzeug_logger(logging.WARNING)
        w_logger = logging.getLogger("werkzeug")
        self.assertEqual(w_logger.level, logging.WARNING)

    def test_config_manager_log_settings(self):
        """驗證 ConfigManager 正確讀取 system_log_file, log_level, log_backup_count 與預設值"""
        cfg_file = os.path.join(self.test_dir, "config.yaml")
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.dump({
                "system_log_file": "custom/system.log",
                "log_level": "DEBUG",
                "log_backup_count": 7
            }, f)

        mgr = ConfigManager(cfg_file)
        self.assertEqual(mgr.get_system_log_file(), "custom/system.log")
        self.assertEqual(mgr.get_log_level(), "DEBUG")
        self.assertEqual(mgr.get_log_backup_count(), 7)

    def test_config_manager_log_settings_defaults(self):
        """驗證 ConfigManager 在無設定時回傳預設值"""
        cfg_file = os.path.join(self.test_dir, "empty_config.yaml")
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.dump({}, f)

        mgr = ConfigManager(cfg_file)
        self.assertEqual(mgr.get_system_log_file(), "logs/system.log")
        self.assertEqual(mgr.get_log_level(), "INFO")
        self.assertEqual(mgr.get_log_backup_count(), 3)


if __name__ == "__main__":
    unittest.main()
