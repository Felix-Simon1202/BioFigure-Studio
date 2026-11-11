"""Chat Completions adapter for built-in synthetic drawing prompts."""

from http.client import HTTPException, HTTPSConnection
from ipaddress import ip_address
import json
import re
import socket
import ssl
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from backend.core.ai_boundary import AiBoundaryError, parse_draft_object
from backend.core.biodot import system_instructions
from backend.core.workbench import CHART_INSTRUCTIONS, MAX_MODEL_RESPONSE, ChartIntent

PRESET_PROMPTS = {
    "scatter": "用科研清晰主题为内置合成样例绘制散点图。",
    "line": "用现代柔和主题为内置合成样例绘制折线图。",
}
PRESET_PROMPTS_EN = {
    "scatter": "Draw a scatter plot for the built-in synthetic sample using the Scientific Clear theme.",
    "line": "Draw a line chart for the built-in synthetic sample using the Modern Soft theme.",
}
_TIMEOUT = 20


class ExternalModelUnavailable(RuntimeError):
    """The configured endpoint could not complete the request."""


class ExternalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, hide_input_in_errors=True)

    base_url: str = Field(min_length=1, max_length=320)
    model: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.:/-]+$")
    api_key: SecretStr = Field(min_length=1, max_length=512)
    preset: Literal["scatter", "line"]
    consent: Literal[True]
    locale: Literal["en", "zh-CN"] = "zh-CN"


def _public_endpoint(base_url: str) -> tuple[str, str, tuple]:
    # Accept named public HTTPS endpoints on port 443, with a plain base path.
    try:
        url = urlsplit(base_url)
        host = url.hostname or ""
        port = url.port
    except ValueError as error:
        raise AiBoundaryError("模型地址格式不正确。") from error
    if (url.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host)
            or port not in (443, None) or url.netloc.lower() not in (host, f"{host}:443")
            or not re.fullmatch(r"(?:/[a-zA-Z0-9_-]+)*/?", url.path) or url.query or url.fragment):
        raise AiBoundaryError("请输入公开 HTTPS 服务的基础地址，例如 https://api.deepseek.com 或兼容服务的 /v1 地址。")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    for _, _, _, _, sockaddr in addresses:
        ip = ip_address(sockaddr[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, "ipv4_mapped", None):
            raise AiBoundaryError("外部模型地址不能指向本机、局域网或保留地址。")
    if not addresses:
        raise ExternalModelUnavailable("未找到外部模型服务地址。")
    path = url.path.rstrip("/")
    if not path.endswith("/chat/completions"):
        path += "/chat/completions"
    return host, path, addresses[0]


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(self, host: str, address: tuple):
        self.address = address
        self.tls = ssl.create_default_context()
        super().__init__(host, timeout=_TIMEOUT, context=self.tls)

    def connect(self) -> None:
        # Use the checked address and authenticate TLS with the original host.
        family, kind, proto, _, sockaddr = self.address
        raw = socket.socket(family, kind, proto)
        try:
            raw.settimeout(_TIMEOUT)
            raw.connect(sockaddr)
            self.sock = self.tls.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def suggest_external_chart(request: ExternalDraftRequest) -> ChartIntent:
    api_key = request.api_key.get_secret_value()
    if not re.fullmatch(r"[!-~]+", api_key):
        raise AiBoundaryError("API Key 包含无效字符。")
    try:
        host, path, address = _public_endpoint(request.base_url)
        body = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": system_instructions(CHART_INSTRUCTIONS + ' JSON example: {"chart_type":"scatter","title":"Synthetic sample","theme_id":"scientific_clear"}')},
                {"role": "user", "content": (PRESET_PROMPTS_EN if request.locale == "en" else PRESET_PROMPTS)[request.preset]},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 384,
            "stream": False,
        }
        if host == "api.deepseek.com":
            body["thinking"] = {"type": "disabled"}
        connection = _PinnedHTTPSConnection(host, address)
        try:
            connection.request("POST", path, body=json.dumps(body).encode("utf-8"),
                               headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
            with connection.getresponse() as response:
                if response.status != 200:
                    raise ExternalModelUnavailable("外部模型请求未成功，请核对服务地址、模型和 API Key。")
                raw = response.read(MAX_MODEL_RESPONSE + 1)
        finally:
            connection.close()
    except TimeoutError:
        raise
    except (HTTPException, OSError) as error:
        raise ExternalModelUnavailable("无法连接外部模型服务，请检查网络和 HTTPS 地址。") from error
    if len(raw) > MAX_MODEL_RESPONSE:
        raise AiBoundaryError("外部模型返回内容超过上限。")
    try:
        choice = json.loads(raw)["choices"][0]
        content = choice["message"]["content"]
    except (UnicodeError, ValueError, KeyError, IndexError, TypeError, RecursionError) as error:
        raise AiBoundaryError("外部模型未返回兼容的草案。") from error
    if choice.get("finish_reason") != "stop" or not isinstance(content, str):
        raise AiBoundaryError("外部模型未返回完整的草案。")
    return ChartIntent.model_validate(parse_draft_object(content))
