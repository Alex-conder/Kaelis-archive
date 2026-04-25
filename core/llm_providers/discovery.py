"""
LLM Provider Discovery
======================
地理定位 + 连通性探测 + 智能推荐。
"""

import time
import logging
from typing import Dict, Any, List, Optional

from core.llm_providers.base import BaseLLMProvider, ProviderRecommendation

logger = logging.getLogger(__name__)

# ============================================================================
# Geo Location
# ============================================================================

class GeoLocator:
    """
    IP 地理定位。

    使用 ip-api.com（免费，无需 API Key）。
    支持本地缓存和降级。
    """

    _cache: Optional[Dict[str, Any]] = None
    _cache_time: float = 0
    _cache_ttl: float = 3600  # 1 小时

    def __init__(self, api_url: str = "http://ip-api.com/json/"):
        self.api_url = api_url

    def get_location(self) -> Dict[str, Any]:
        """
        返回当前网络位置的地理信息。

        Returns:
            {"country": "CN", "city": "Hangzhou", "region": "Zhejiang",
             "lat": 30.0, "lon": 120.0, "isp": "..."}
            失败时返回 {"country": "unknown", ...}
        """
        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        try:
            import requests
            resp = requests.get(self.api_url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "success":
                location = {
                    "country": data.get("countryCode", "unknown"),
                    "city": data.get("city", "unknown"),
                    "region": data.get("regionName", "unknown"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "isp": data.get("isp", "unknown"),
                }
                self._cache = location
                self._cache_time = now
                logger.info("Geo location detected: %s, %s", location["city"], location["country"])
                return location
        except Exception as e:
            logger.warning("Geo location failed: %s", e)

        fallback = {"country": "unknown", "city": "unknown", "region": "unknown"}
        self._cache = fallback
        self._cache_time = now
        return fallback


# ============================================================================
# Provider Detector
# ============================================================================

class ProviderDetector:
    """
    探测所有 Provider 的连通性和延迟。
    """

    def probe_all(self, providers: List[BaseLLMProvider]) -> Dict[str, Dict[str, Any]]:
        """
        批量探测 Provider。

        Returns:
            {"deepseek": {"available": True, "latency_ms": 45}, ...}
        """
        results: Dict[str, Dict[str, Any]] = {}
        for provider in providers:
            try:
                available = provider.is_available()
                latency = provider.get_latency_ms() if available else -1
                results[provider.name] = {
                    "available": available,
                    "latency_ms": latency,
                    "display_name": provider.display_name,
                    "region_hint": provider.region_hint,
                    "requires_api_key": provider.requires_api_key,
                }
            except Exception as e:
                logger.debug("Probe failed for %s: %s", provider.name, e)
                results[provider.name] = {
                    "available": False,
                    "latency_ms": -1,
                    "display_name": provider.display_name,
                    "region_hint": provider.region_hint,
                    "requires_api_key": provider.requires_api_key,
                }
        return results


# ============================================================================
# Provider Recommender
# ============================================================================

class ProviderRecommender:
    """
    根据地理位置和探测结果，生成 Provider 推荐排序。
    """

    # 区域匹配加分权重
    REGION_MATCH_SCORE = 20
    LATENCY_BASELINE_MS = 100
    OLLAMA_BONUS = 30  # 本地模型优先

    def __init__(self, locator: Optional[GeoLocator] = None, detector: Optional[ProviderDetector] = None):
        self.locator = locator or GeoLocator()
        self.detector = detector or ProviderDetector()

    def recommend(
        self,
        providers: List[BaseLLMProvider],
        location: Optional[Dict[str, Any]] = None,
    ) -> List[ProviderRecommendation]:
        """
        生成 Provider 推荐列表（按分数降序）。
        """
        if location is None:
            location = self.locator.get_location()

        probe_results = self.detector.probe_all(providers)
        recommendations: List[ProviderRecommendation] = []

        country = location.get("country", "unknown").upper()
        city = location.get("city", "unknown").lower()

        for provider in providers:
            result = probe_results.get(provider.name, {})
            available = result.get("available", False)
            latency_ms = result.get("latency_ms", -1)

            score = self._calculate_score(
                available=available,
                latency_ms=latency_ms,
                provider=provider,
                country=country,
                city=city,
            )

            reason = self._build_reason(
                available=available,
                latency_ms=latency_ms,
                provider=provider,
                country=country,
                score=score,
            )

            recommendations.append(
                ProviderRecommendation(
                    name=provider.name,
                    display_name=provider.display_name,
                    score=score,
                    latency_ms=latency_ms if latency_ms > 0 else 9999,
                    reason=reason,
                    region_hint=provider.region_hint,
                    requires_api_key=provider.requires_api_key,
                    base_url=provider.base_url,
                    default_model=provider.default_model,
                )
            )

        # 按分数降序，不可用排最后
        recommendations.sort(key=lambda r: (r.score, -r.latency_ms), reverse=True)
        return recommendations

    def _calculate_score(
        self,
        available: bool,
        latency_ms: int,
        provider: BaseLLMProvider,
        country: str,
        city: str,
    ) -> int:
        if not available:
            return 0

        score = 50  # 基础可用分

        # 1. 区域匹配
        region = provider.region_hint.lower()
        if country == "CN" and "cn" in region:
            score += self.REGION_MATCH_SCORE
            # 城市精确匹配（如 hangzhou）
            if city and city in region:
                score += 10
        elif country != "CN" and "global" in region:
            score += self.REGION_MATCH_SCORE

        # 2. 延迟加分
        if latency_ms > 0:
            latency_bonus = max(0, int((self.LATENCY_BASELINE_MS - latency_ms) / 5))
            score += latency_bonus

        # 3. Ollama 本地模型额外加分
        if provider.name == "ollama":
            score += self.OLLAMA_BONUS

        # 4. 无需 API Key 的额外加分（零成本）
        if not provider.requires_api_key:
            score += 10

        return min(score, 100)

    def _build_reason(
        self,
        available: bool,
        latency_ms: int,
        provider: BaseLLMProvider,
        country: str,
        score: int,
    ) -> str:
        if not available:
            if not provider.requires_api_key:
                return "服务未运行或无法连接"
            return "API Key 未配置或服务不可达"

        parts: List[str] = []
        if latency_ms > 0:
            parts.append(f"延迟 {latency_ms}ms")
        if provider.name == "ollama":
            parts.append("本地运行，零成本")
        elif not provider.requires_api_key:
            parts.append("无需 API Key")
        elif "cn" in provider.region_hint:
            parts.append("国内节点")
        else:
            parts.append("国际节点")

        if country == "CN" and "global" in provider.region_hint and provider.requires_api_key:
            parts.append("国内访问可能受限，建议配置代理")

        return "，".join(parts) if parts else "可用"

    def get_guidance(self, recommendations: List[ProviderRecommendation]) -> str:
        """
        生成面向用户的引导文本（Markdown 格式）。
        """
        if not recommendations:
            return "未检测到任何可用的大模型服务。请配置 API Key 或启动 Ollama 本地服务。"

        lines = ["## 🔍 Kaelis 检测到以下可用的大模型服务\n"]
        top = [r for r in recommendations if r.score > 0][:5]
        for i, r in enumerate(top, 1):
            badge = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            key_info = f"`{r.name}`" if not r.requires_api_key else f"`{r.name}`（需 API Key）"
            lines.append(f"{badge} **{r.display_name}** {key_info}")
            lines.append(f"   - 推荐原因：{r.reason}")
            lines.append(f"   - 默认模型：`{r.default_model}`")
            lines.append(f"   - 接口地址：`{r.base_url}`")
            lines.append("")

        # 环境变量引导
        lines.append("---")
        lines.append("### 快速接入")
        for r in top[:3]:
            if r.requires_api_key:
                env_key = f"{r.name.upper()}_API_KEY"
                lines.append(f"- **{r.display_name}**: 设置环境变量 `{env_key}=your-key`")

        if any(r.name == "ollama" for r in top):
            lines.append("- **Ollama**: 安装并运行 `ollama run llama3.1`，Kaelis 将自动连接")

        return "\n".join(lines)
