"""
API Proxy (Prompt 7)

Secure proxy for LLM agents to call user APIs.
Integrates CredentialVault, RiskAwareGateway, and SafetyScanner.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Sensitive patterns for response filtering
_SENSITIVE_RESPONSE_PATTERNS = [
    (r'"api_key"\s*:\s*"[^"]{8,}"', '"api_key":"***"'),
    (r'"token"\s*:\s*"[^"]{8,}"', '"token":"***"'),
    (r'"password"\s*:\s*"[^"]+"', '"password":"***"'),
    (r'"secret"\s*:\s*"[^"]{8,}"', '"secret":"***"'),
    (r'sk-[a-zA-Z0-9]{20,}', '***'),
    (r'Bearer\s+[a-zA-Z0-9_-]{20,}', 'Bearer ***'),
]


class APIProxy:
    """
    Secure API proxy for agent-to-user-service calls.

    Usage:
        proxy = APIProxy(vault, gateway)
        result = await proxy.call_user_api(agent_id, user_id, "openai", "/v1/chat/completions", {...})
    """

    def __init__(self, vault, gateway):
        self.vault = vault
        self.gateway = gateway

    async def call_user_api(
        self,
        agent_id: str,
        user_id: str,
        service_name: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call a user API securely through the proxy.

        Steps:
            1. Retrieve credential from vault
            2. Pre-flight risk evaluation
            3. Execute HTTP request
            4. Post-flight sensitive data filtering
            5. Audit log
        """
        params = params or {}

        # Step 1: Retrieve credential
        try:
            api_key = self.vault.retrieve_credential(user_id, service_name)
        except Exception as e:
            logger.warning(f"Credential retrieval failed for {user_id}/{service_name}: {e}")
            return {"success": False, "error": "Credential not found", "stage": "credential"}

        # Step 2: Pre-flight risk evaluation
        try:
            from core.security.risk_gateway import RiskDecision
            decision, reason, approval_id = await self.gateway.evaluate(
                source_id=agent_id,
                operation="api_call",
                data={"service_name": service_name, "endpoint": endpoint, "params": params},
            )
            if decision == RiskDecision.BLOCK:
                logger.warning(f"API call blocked by gateway: {reason}")
                return {"success": False, "error": f"Blocked: {reason}", "stage": "risk_gate"}
            if decision == RiskDecision.CONFIRM:
                logger.info(f"API call requires approval: {approval_id}")
                return {
                    "success": False,
                    "error": f"Requires approval: {reason}",
                    "stage": "risk_gate",
                    "approval_id": approval_id,
                }
        except Exception as e:
            logger.warning(f"Risk evaluation failed: {e}")
            return {"success": False, "error": f"Risk evaluation error: {e}", "stage": "risk_gate"}

        # Step 3: Execute HTTP request
        try:
            response_data = self._execute_request(service_name, endpoint, params, api_key)
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return {"success": False, "error": f"HTTP error: {e}", "stage": "http"}

        # Step 4: Post-flight sensitive data filtering
        filtered_response = self._filter_sensitive(response_data)

        # Step 5: Audit log
        logger.info(f"API proxy call: agent={agent_id} service={service_name} endpoint={endpoint} status=success")

        return {
            "success": True,
            "data": filtered_response,
            "service_name": service_name,
            "endpoint": endpoint,
        }

    def _execute_request(self, service_name: str, endpoint: str, params: Dict[str, Any], api_key: str) -> Any:
        """Execute the actual HTTP request."""
        # Determine base URL from service_name
        base_urls = {
            "openai": "https://api.openai.com",
            "claude": "https://api.anthropic.com",
            "deepseek": "https://api.deepseek.com",
        }
        base_url = base_urls.get(service_name, f"https://{service_name}.com")
        url = f"{base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # Try requests first, fallback to urllib
        try:
            import requests
            response = requests.post(url, headers=headers, json=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback to urllib
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(params).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _filter_sensitive(self, data: Any) -> Any:
        """Filter sensitive information from API response."""
        text = json.dumps(data, ensure_ascii=False, default=str)
        for pattern, replacement in _SENSITIVE_RESPONSE_PATTERNS:
            text = re.sub(pattern, replacement, text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
