"""
tests/mock_llm_server.py
Billiam OS — Mock OpenAI-Compatible LLM Server for Integration Tests.

A minimal HTTP server implementing the chat completions endpoint
(openai-like) that returns configurable canned responses.

Usage:
    server = MockLLMServer(port=8099)
    server.start()

    # Configure response
    server.set_response("TOOL: echo hello")

    # Client points at it
    client = OpenAI(base_url="http://localhost:8099/v1", api_key="test")
    ...
"""

import json
import logging
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger("mock_llm")

# Default canned responses — first call returns first, then cycles
DEFAULT_RESPONSES = [
    "Hello! I am Billiam, your personal digital butler. How may I assist you today?",
    "TOOL: echo 'integration test successful'",
]


class MockLLMHandler(BaseHTTPRequestHandler):
    """HTTP handler that mimics the OpenAI chat completions endpoint."""

    # Shared state across instances (set by the server)
    responses: list[str] = list(DEFAULT_RESPONSES)
    call_count: int = 0
    last_request: dict | None = None
    on_request: Callable | None = None

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        request_data = json.loads(body)
        type(self).last_request = request_data
        type(self).call_count += 1

        if type(self).on_request is not None:
            type(self).on_request(request_data)

        # Pick response (round-robin through available responses)
        idx = min(type(self).call_count - 1, len(type(self).responses) - 1)
        response_text = type(self).responses[idx]

        resp = {
            "id": "chatcmpl-mock-001",
            "object": "chat.completion",
            "created": 1000000,
            "model": request_data.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def log_message(self, format, *args):
        logger.debug(format, *args)


class MockLLMServer:
    """Manages a MockLLMHandler in a background thread."""

    def __init__(self, port: int = 8099, responses: list[str] | None = None):
        self.port = port
        self.server = HTTPServer(("localhost", port), MockLLMHandler)
        self._thread: threading.Thread | None = None
        MockLLMHandler.call_count = 0
        MockLLMHandler.last_request = None
        MockLLMHandler.on_request = None
        if responses is not None:
            MockLLMHandler.responses = list(responses)

    def set_responses(self, responses: list[str]):
        """Set canned responses for subsequent calls."""
        MockLLMHandler.responses = list(responses)

    def set_on_request(self, callback: Callable):
        """Set a callback fired on each request."""
        MockLLMHandler.on_request = callback

    @property
    def call_count(self) -> int:
        return MockLLMHandler.call_count

    @property
    def last_request(self) -> dict | None:
        return MockLLMHandler.last_request

    @property
    def api_base(self) -> str:
        return f"http://localhost:{self.port}/v1"

    def start(self):
        """Start the server in a daemon thread."""
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the server."""
        self.server.shutdown()
        if self._thread:
            self._thread.join(timeout=2)

    @classmethod
    def _reset(cls):
        """Reset shared state between tests."""
        MockLLMHandler.call_count = 0
        MockLLMHandler.last_request = None
        MockLLMHandler.on_request = None
