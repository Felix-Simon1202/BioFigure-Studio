"""Minimal MCP stdio bridge for the paired local drawing connector."""

from base64 import b64encode
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
import json
import os
import re
import sys
from urllib.parse import urlencode, urlsplit

from backend.core.workbench_connector import CONNECTOR_PREFIX


PROTOCOLS = ("2025-11-25", "2025-06-18")
MAX_MESSAGE = 16 * 1024
MAX_ARTIFACT = 4 * 1024 * 1024
FILE_TYPES = frozenset({
    "application/pdf", "application/vnd.biofigure.project+zip", "image/png", "image/svg+xml", "image/tiff",
})


class BridgeError(ValueError):
    pass


class PairedClient:
    def __init__(self, url: str, token: str):
        try:
            address = urlsplit(url)
            port = address.port
        except ValueError:
            raise BridgeError("本机连接地址无效。") from None
        if (address.scheme != "http" or port is None
                or address.netloc != f"127.0.0.1:{port}"
                or address.path != CONNECTOR_PREFIX or address.query or address.fragment):
            raise BridgeError("只接受工作台生成的本机连接地址。")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise BridgeError("请提供有效的工作台连接码。")
        self.port = port
        self.token = token

    def request(self, method: str, suffix: str = "", payload: dict | None = None) -> tuple[bytes, str]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Authorization": "Bearer " + self.token}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            try:
                body = json.dumps(payload, allow_nan=False).encode("utf-8")
            except (ValueError, RecursionError) as error:
                raise BridgeError("工具参数包含无效 JSON 数据。") from error
        try:
            connection.request(method, CONNECTOR_PREFIX + suffix, body=body, headers=headers)
            with connection.getresponse() as response:
                if response.status == 401:
                    raise BridgeError("连接已失效，请在工作台重新配对。")
                if response.status not in (200, 201, 202):
                    raise BridgeError(f"工作台拒绝操作（HTTP {response.status}）。")
                output = response.read(MAX_ARTIFACT + 1)
                if len(output) > MAX_ARTIFACT:
                    raise BridgeError("连接返回的成品超过 4 MiB。")
                return output, response.getheader("Content-Type", "").split(";", 1)[0]
        except (HTTPException, OSError):
            raise BridgeError("无法访问本机工作台。") from None
        finally:
            connection.close()


class McpSession:
    def __init__(self, client: PairedClient):
        self.client = client
        self.negotiated = False
        self.initialized = False
        self.catalog: dict[str, dict] | None = None

    @staticmethod
    def _json_object(output: bytes) -> dict:
        try:
            value = json.loads(output)
        except (UnicodeError, ValueError, RecursionError):
            raise BridgeError("本机工作台返回了无效响应。") from None
        if not isinstance(value, dict):
            raise BridgeError("本机工作台返回了无效响应。")
        return value

    def _load_catalog(self) -> dict[str, dict]:
        output, _ = self.client.request("GET")
        actions = self._json_object(output).get("actions")
        if not isinstance(actions, list) or len(actions) > 64:
            raise BridgeError("本机工具目录无效。")
        catalog = {}
        for action in actions:
            if not isinstance(action, dict):
                raise BridgeError("本机工具目录无效。")
            name, path = action.get("name"), action.get("path")
            schema, description = action.get("input_schema"), action.get("description")
            if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
                    or name in catalog or not isinstance(path, str)
                    or not re.fullmatch(re.escape(CONNECTOR_PREFIX) + r"/[a-z-]+", path)
                    or action.get("method") not in ("GET", "POST", "DELETE")
                    or action.get("output", "json") not in ("json", "file")
                    or not isinstance(schema, dict) or schema.get("type") != "object"
                    or not isinstance(description, str)):
                raise BridgeError("本机工具目录无效。")
            catalog[name] = action
        self.catalog = catalog
        return catalog

    def _tools(self) -> dict:
        return {"tools": [
            {"name": action["name"], "description": action["description"], "inputSchema": action["input_schema"]}
            for action in self._load_catalog().values()
        ]}

    def _call(self, params: dict) -> dict:
        name, args = params.get("name"), params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(args, dict):
            raise BridgeError("工具名称与参数无效。")
        catalog = self.catalog if self.catalog is not None else self._load_catalog()
        action = catalog.get(name)
        if action is None:
            raise BridgeError("未知工作台工具。")
        schema = action["input_schema"]
        properties, required = schema.get("properties", {}), schema.get("required", [])
        if (not isinstance(properties, dict) or not isinstance(required, list)
                or any(not isinstance(key, str) for key in required)
                or set(args) - set(properties) or set(required) - set(args)):
            raise BridgeError("工具参数不符合工作台目录。")
        method = action["method"]
        suffix = action["path"].removeprefix(CONNECTOR_PREFIX)
        if method != "POST" and args:
            if any(type(value) not in (str, int, float, bool) for value in args.values()):
                raise BridgeError("查询参数必须使用简单值。")
            suffix += "?" + urlencode(args)
        output, content_type = self.client.request(method, suffix, args if method == "POST" else None)
        if action.get("output") == "file":
            if content_type not in FILE_TYPES:
                raise BridgeError("连接返回了不支持的成品类型。")
            return {"content": [{"type": "resource", "resource": {
                "uri": f"biofigure://artifact/{sha256(output).hexdigest()}",
                "mimeType": content_type,
                "blob": b64encode(output).decode("ascii"),
            }}]}
        return {"content": [{"type": "text", "text": json.dumps(self._json_object(output), ensure_ascii=False)}]}

    def dispatch(self, message: object) -> dict | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return self._error(None, -32600, "Invalid request")
        method, identifier = message["method"], message.get("id")
        if "id" not in message:
            if method == "notifications/initialized" and self.negotiated:
                self.initialized = True
            return None
        if type(identifier) not in (str, int):
            return self._error(None, -32600, "Invalid request ID")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return self._error(identifier, -32602, "Invalid params")
        if method == "initialize":
            if self.negotiated or not isinstance(params.get("protocolVersion"), str):
                return self._error(identifier, -32602, "Invalid initialization")
            version = params["protocolVersion"]
            self.negotiated = True
            result = {
                "protocolVersion": version if version in PROTOCOLS else PROTOCOLS[0],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "biofigure-workbench", "version": "1.0.0"},
            }
        elif method == "ping":
            result = {}
        elif not self.initialized:
            return self._error(identifier, -32002, "Initialize the MCP connection first")
        elif method == "tools/list":
            try:
                result = self._tools()
            except BridgeError as error:
                return self._error(identifier, -32001, str(error))
        elif method == "tools/call":
            try:
                result = self._call(params)
            except BridgeError as error:
                result = {"isError": True, "content": [{"type": "text", "text": str(error)}]}
        else:
            return self._error(identifier, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": identifier, "result": result}

    @staticmethod
    def _error(identifier, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def main() -> int:
    try:
        client = PairedClient(os.environ.get("BIOFIGURE_CONNECTOR_URL", ""), os.environ.get("BIOFIGURE_CONNECTOR_TOKEN", ""))
    except BridgeError as error:
        print(error, file=sys.stderr)
        return 2
    session = McpSession(client)
    while line := sys.stdin.buffer.readline(MAX_MESSAGE + 1):
        if len(line) > MAX_MESSAGE:
            print("MCP input exceeds 16 KiB.", file=sys.stderr)
            return 2
        try:
            message = json.loads(line)
        except (UnicodeError, ValueError, RecursionError):
            response = session._error(None, -32700, "Parse error")
        else:
            response = session.dispatch(message)
        if response is not None:
            sys.stdout.buffer.write(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
            sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
