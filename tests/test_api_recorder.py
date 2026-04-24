"""
Recorder API 单元测试
"""

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_base import FlaskAppTestBase


class TestRecorderAPI(FlaskAppTestBase):
    """测试录屏 API"""
    
    def test_get_status(self):
        """GET /api/recorder/status"""
        r = self.json_get('/api/recorder/status')
        data = self.assert_json_success(r)
        payload = data.get("data", data)
        self.assertIn("current_session", payload)
    
    def test_start_recording(self):
        """POST /api/recorder/start"""
        r = self.json_post('/api/recorder/start', {
            "name": "test_recording",
            "capture_screenshots": False
        })
        self.assertIn(r.status_code, [200, 503])
    
    def test_stop_recording_not_started(self):
        """POST /api/recorder/stop 未开始录制"""
        r = self.json_post('/api/recorder/stop', {})
        self.assertIn(r.status_code, [200, 400, 503])
    
    def test_list_recordings(self):
        """GET /api/recorder/recordings"""
        r = self.json_get('/api/recorder/recordings')
        self.assertIn(r.status_code, [200, 503])
    
    def test_get_recording_detail(self):
        """GET /api/recorder/recordings/<id>"""
        r = self.json_get('/api/recorder/recordings/nonexistent')
        self.assertIn(r.status_code, [200, 404, 503])
    
    def test_delete_recording(self):
        """DELETE /api/recorder/recordings/<id>"""
        r = self.client.delete('/api/recorder/recordings/nonexistent')
        self.assertIn(r.status_code, [200, 404])
    
    def test_play_recording(self):
        """POST /api/recorder/play/<id>"""
        r = self.json_post('/api/recorder/play/test', {})
        self.assertIn(r.status_code, [200, 404, 503])
    
    def test_start_and_stop_recording(self):
        """完整的录制流程"""
        # 开始录制
        r1 = self.json_post('/api/recorder/start', {"name": "test_session"})
        self.assertIn(r1.status_code, [200, 409, 503])
        
        if r1.status_code == 200:
            # 停止录制
            r2 = self.json_post('/api/recorder/stop', {})
            self.assertIn(r2.status_code, [200, 500])
            
            if r2.status_code == 200:
                data = r2.get_json()
                self.assertTrue(data.get("success", False))
    
    def test_convert_to_skill_not_found(self):
        """POST /api/recorder/convert-to-skill/<id> 录制不存在"""
        r = self.json_post('/api/recorder/convert-to-skill/nonexistent', {})
        self.assertIn(r.status_code, [404, 503])

    def test_start_recording_already_recording(self):
        """已经在录制时返回 409"""
        from unittest.mock import patch
        with patch("api.routes.recorder._recording_status", {"is_recording": True, "current_session": {"id": "x"}, "last_recording": None}):
            r = self.json_post('/api/recorder/start', {"name": "test"})
            self.assertIn(r.status_code, [409, 503])

    def test_stop_recording_not_recording(self):
        """未录制时停止返回 400"""
        from unittest.mock import patch
        with patch("api.routes.recorder._recording_status", {"is_recording": False, "current_session": None, "last_recording": None}):
            with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
                r = self.json_post('/api/recorder/stop', {})
                self.assertIn(r.status_code, [400, 503])

    def test_start_when_recorder_unavailable(self):
        """RECORDER_AVAILABLE=False 时返回 503"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", False):
            r = self.json_post('/api/recorder/start', {})
            self.assertEqual(r.status_code, 503)
            data = r.get_json()
            self.assertFalse(data.get("success"))

    def test_play_when_recorder_unavailable(self):
        """播放器不可用时返回 503"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", False):
            r = self.json_post('/api/recorder/play/test', {})
            self.assertEqual(r.status_code, 503)

    def test_list_when_recorder_unavailable(self):
        """录制器不可用时列表返回 503"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", False):
            r = self.json_get('/api/recorder/recordings')
            self.assertEqual(r.status_code, 503)

    def test_get_when_recorder_unavailable(self):
        """录制器不可用时详情返回 503"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", False):
            r = self.json_get('/api/recorder/recordings/test')
            self.assertEqual(r.status_code, 503)

    def test_start_recording_exception(self):
        """get_recorder 抛出异常返回 500"""
        from unittest.mock import patch
        with patch("api.routes.recorder._recording_status", {"is_recording": False, "current_session": None, "last_recording": None}):
            with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
                with patch("api.routes.recorder.get_recorder", side_effect=RuntimeError("boom")):
                    r = self.json_post('/api/recorder/start', {"name": "test"})
                    self.assertEqual(r.status_code, 500)

    def test_list_recordings_exception(self):
        """get_recorder 抛出异常返回 500"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
            with patch("api.routes.recorder.get_recorder", side_effect=RuntimeError("boom")):
                r = self.json_get('/api/recorder/recordings')
                self.assertEqual(r.status_code, 500)

    def test_get_recording_exception(self):
        """get_recorder 抛出异常返回 500"""
        from unittest.mock import patch
        with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
            with patch("api.routes.recorder.get_recorder", side_effect=RuntimeError("boom")):
                r = self.json_get('/api/recorder/recordings/test')
                self.assertEqual(r.status_code, 500)

    def test_stop_recording_failed(self):
        """stop_recording 返回 None 返回 500"""
        from unittest.mock import patch, MagicMock
        mock_recorder = MagicMock()
        mock_recorder.stop_recording.return_value = None
        with patch("api.routes.recorder._recording_status", {"is_recording": True, "current_session": {"id": "x"}, "last_recording": None}):
            with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
                with patch("api.routes.recorder.get_recorder", return_value=mock_recorder):
                    r = self.json_post('/api/recorder/stop', {})
                    self.assertEqual(r.status_code, 500)

    def test_play_recording_exception(self):
        """load_recording 抛出异常返回 500"""
        from unittest.mock import patch, MagicMock
        mock_recorder = MagicMock()
        mock_recorder.load_recording.side_effect = RuntimeError("boom")
        with patch("api.routes.recorder.RECORDER_AVAILABLE", True):
            with patch("api.routes.recorder.get_recorder", return_value=mock_recorder):
                r = self.json_post('/api/recorder/play/test', {})
                self.assertEqual(r.status_code, 500)

    def test_convert_to_skill_exception(self):
        """get_recorder 抛出异常返回 500"""
        from unittest.mock import patch
        with patch("api.routes.recorder.get_recorder", side_effect=RuntimeError("boom")):
            r = self.json_post('/api/recorder/convert-to-skill/test', {})
            self.assertEqual(r.status_code, 500)


if __name__ == "__main__":
    unittest.main()
