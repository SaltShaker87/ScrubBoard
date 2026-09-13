"""Stand-in for llama-server used by the LLM tests: /health plus streaming chat
completions that tag every "Zelda" as a first_name. Honors LLAMA_API_KEY and
FAKE_LLAMA_DELAY (seconds per streamed piece)."""
import argparse
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args, _unknown = parser.parse_known_args()
    key = os.environ.get("LLAMA_API_KEY", "")
    delay = float(os.environ.get("FAKE_LLAMA_DELAY", "0"))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()

        def do_POST(self):
            if self.headers.get("Authorization") != f"Bearer {key}":
                self.send_response(401)
                self.end_headers()
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            prompt = body["messages"][-1]["content"]
            text = prompt.split("Text: ", 1)[-1].rsplit("\n\nProvide", 1)[0]
            tagged = re.sub(r"\bZelda\b", "[Zelda]first_name", text)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(0, len(tagged), 8):
                time.sleep(delay)
                piece = {"choices": [{"delta": {"content": tagged[i:i + 8]}}]}
                self.wfile.write(b"data: " + json.dumps(piece).encode() + b"\n\n")
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
