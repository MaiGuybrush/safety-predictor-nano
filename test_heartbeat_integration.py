import os
import unittest
from unittest.mock import MagicMock, patch

from main import start_heartbeat_services, stop_heartbeat_services


class TestHeartbeatIntegration(unittest.TestCase):

    def test_start_heartbeat_disabled(self):
        config = {
            "heartbeat": {"enabled": False}
        }
        services = start_heartbeat_services(config, [{"camera_id": "cam1", "url": "rtsp://cam1"}])
        self.assertEqual(services, [])

    def test_start_heartbeat_streams(self):
        config = {
            "heartbeat": {
                "enabled": True,
                "ap_name": "TestSafetyNano",
                "interval_seconds": 30,
                "version": "1.2.3",
                "agent_port": 8080,
            }
        }
        stream_units = [
            {"camera_id": "cam-001", "url": "rtsp://127.0.0.1/cam-001"},
            {"camera_id": "cam-002", "url": "rtsp://127.0.0.1/cam-002"},
        ]

        with patch("argus_eventlog.heartbeat.HeartbeatService._send_heartbeat", return_value=True):
            services = start_heartbeat_services(config, stream_units, mode="rtsp")
            self.assertEqual(len(services), 2)

            self.assertEqual(services[0].ap_name, "TestSafetyNano")
            self.assertEqual(services[0].instance, "cam-001")
            self.assertEqual(services[0].camera_id, "cam-001")
            self.assertEqual(services[0].interval_seconds, 30)
            self.assertEqual(services[0].version, "1.2.3")
            self.assertTrue(services[0].event_output_path.endswith(os.path.normpath("cam-001/events")))
            self.assertTrue(services[0].is_running())

            self.assertEqual(services[1].instance, "cam-002")
            self.assertEqual(services[1].camera_id, "cam-002")
            self.assertTrue(services[1].is_running())

            stop_heartbeat_services(services)
            self.assertFalse(services[0].is_running())
            self.assertFalse(services[1].is_running())

    def test_start_heartbeat_video_mode(self):
        config = {
            "heartbeat": {
                "enabled": True,
                "ap_name": "TestSafetyNano",
                "version": "0.1.0",
            },
            "camera_id": "my_video_cam",
        }

        with patch("argus_eventlog.heartbeat.HeartbeatService._send_heartbeat", return_value=True):
            services = start_heartbeat_services(config, [], mode="video", video_camera_id="my_video_cam")
            self.assertEqual(len(services), 1)
            self.assertEqual(services[0].instance, "my_video_cam")
            self.assertEqual(services[0].camera_id, "my_video_cam")
            self.assertTrue(services[0].event_output_path.endswith(os.path.normpath("my_video_cam/events")))
            self.assertTrue(services[0].is_running())

            stop_heartbeat_services(services)
            self.assertFalse(services[0].is_running())


if __name__ == "__main__":
    unittest.main()
