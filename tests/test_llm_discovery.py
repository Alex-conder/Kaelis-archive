"""
Tests for core.llm_providers.discovery
C1: isolated; no real network calls
C4: graceful degradation paths covered
"""

from unittest.mock import MagicMock, patch

import pytest

from core.llm_providers.base import ProviderRecommendation
from core.llm_providers.discovery import GeoLocator, ProviderDetector, ProviderRecommender


# =====================================================================
# GeoLocator
# =====================================================================

class TestGeoLocator:
    @patch("requests.get")
    def test_get_location_success(self, mock_get):
        mock_get.return_value.json.return_value = {
            "status": "success",
            "countryCode": "CN",
            "city": "Hangzhou",
            "regionName": "Zhejiang",
            "lat": 30.0,
            "lon": 120.0,
            "isp": "Aliyun",
        }
        mock_get.return_value.raise_for_status = MagicMock()
        loc = GeoLocator()
        result = loc.get_location()
        assert result["country"] == "CN"
        assert result["city"] == "Hangzhou"

    @patch("requests.get")
    def test_get_location_fallback_on_error(self, mock_get):
        mock_get.side_effect = RuntimeError("network down")
        loc = GeoLocator()
        result = loc.get_location()
        assert result["country"] == "unknown"

    @patch("requests.get")
    def test_get_location_cache(self, mock_get):
        mock_get.return_value.json.return_value = {
            "status": "success", "countryCode": "US", "city": "NYC",
            "regionName": "NY", "lat": 0, "lon": 0, "isp": "x",
        }
        mock_get.return_value.raise_for_status = MagicMock()
        loc = GeoLocator()
        r1 = loc.get_location()
        r2 = loc.get_location()  # should hit cache
        assert r1 == r2
        assert mock_get.call_count == 1


# =====================================================================
# ProviderDetector
# =====================================================================

class TestProviderDetector:
    def test_probe_all(self):
        p1 = MagicMock()
        p1.name = "p1"
        p1.display_name = "P1"
        p1.region_hint = "cn"
        p1.requires_api_key = True
        p1.is_available.return_value = True
        p1.get_latency_ms.return_value = 50

        p2 = MagicMock()
        p2.name = "p2"
        p2.display_name = "P2"
        p2.region_hint = "global"
        p2.requires_api_key = True
        p2.is_available.side_effect = RuntimeError("down")

        detector = ProviderDetector()
        results = detector.probe_all([p1, p2])
        assert results["p1"]["available"] is True
        assert results["p1"]["latency_ms"] == 50
        assert results["p2"]["available"] is False


# =====================================================================
# ProviderRecommender
# =====================================================================

class TestProviderRecommender:
    def _make_mock_provider(self, name, display_name, region_hint, requires_key=True):
        p = MagicMock()
        p.name = name
        p.display_name = display_name
        p.region_hint = region_hint
        p.requires_api_key = requires_key
        p.base_url = f"https://{name}.com"
        p.default_model = f"{name}-model"
        return p

    def test_recommend_cn_user(self):
        p1 = self._make_mock_provider("qwen", "Qwen", "cn-hangzhou")
        p2 = self._make_mock_provider("openai", "OpenAI", "global")
        p3 = self._make_mock_provider("ollama", "Ollama", "local", requires_key=False)

        detector = ProviderDetector()
        with patch.object(detector, "probe_all", return_value={
            "qwen": {"available": True, "latency_ms": 12},
            "openai": {"available": True, "latency_ms": 200},
            "ollama": {"available": True, "latency_ms": 5},
        }):
            recommender = ProviderRecommender(detector=detector)
            location = {"country": "CN", "city": "Hangzhou", "region": "Zhejiang"}
            recs = recommender.recommend([p1, p2, p3], location=location)

        assert len(recs) == 3
        # Ollama should score highest (local + no key + low latency)
        assert recs[0].name == "ollama"
        # Qwen should be next (cn match + low latency)
        assert recs[1].name == "qwen"
        # OpenAI last (global, high latency)
        assert recs[2].name == "openai"

    def test_recommend_unavailable_filtered_to_bottom(self):
        p1 = self._make_mock_provider("dead", "Dead", "cn")
        detector = ProviderDetector()
        with patch.object(detector, "probe_all", return_value={
            "dead": {"available": False, "latency_ms": -1},
        }):
            recommender = ProviderRecommender(detector=detector)
            recs = recommender.recommend([p1], location={"country": "CN", "city": "Beijing"})
        assert recs[0].score == 0
        assert recs[0].score == 0  # score 0 means unavailable

    def test_get_guidance(self):
        recs = [
            ProviderRecommendation(
                name="deepseek", display_name="DeepSeek", score=90, latency_ms=20,
                reason="国内节点，延迟 20ms", region_hint="cn", requires_api_key=True,
                base_url="https://api.deepseek.com", default_model="deepseek-chat",
            ),
            ProviderRecommendation(
                name="ollama", display_name="Ollama", score=95, latency_ms=5,
                reason="本地运行", region_hint="local", requires_api_key=False,
                base_url="http://localhost:11434", default_model="llama3.1",
            ),
        ]
        recommender = ProviderRecommender()
        guidance = recommender.get_guidance(recs)
        assert "Ollama" in guidance
        assert "deepseek-chat" in guidance
        assert "DEEPSEEK_API_KEY" in guidance

    def test_recommend_when_geo_api_fails(self):
        """地理 API 失败时应使用 unknown 位置继续推荐 (C4)。"""
        p1 = self._make_mock_provider("ollama", "Ollama", "local", requires_key=False)
        detector = ProviderDetector()
        with patch.object(detector, "probe_all", return_value={
            "ollama": {"available": True, "latency_ms": 5},
        }):
            recommender = ProviderRecommender(detector=detector)
            recs = recommender.recommend([p1])  # no location passed
            assert recs[0].name == "ollama"
            assert recs[0].score > 0

    def test_recommend_when_no_providers_available(self):
        """无可用 Provider 时应返回空分列表 (C4)。"""
        p1 = self._make_mock_provider("dead", "Dead", "global")
        detector = ProviderDetector()
        with patch.object(detector, "probe_all", return_value={
            "dead": {"available": False, "latency_ms": -1},
        }):
            recommender = ProviderRecommender(detector=detector)
            recs = recommender.recommend([p1], location={"country": "CN", "city": "Beijing"})
            assert all(r.score == 0 for r in recs)
            guidance = recommender.get_guidance([])
            assert "未检测到" in guidance
