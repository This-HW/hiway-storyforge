"""Stdlib HTTP server: JSON API + static UI. Run: python -m storyforge.web"""
from __future__ import annotations

import base64
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import ROOT, data_dir, load_config
from .models import TOPICS
from .rules import MANUAL_CHECK_ITEMS
from .services import Pipeline

CFG = load_config()
DATA = data_dir(CFG)
PIPE = Pipeline(CFG, DATA)
WEB_DIR = ROOT / "web"


def _json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    # -- helpers ------------------------------------------------------------
    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_file(self, path: Path, content_type: str | None = None):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         content_type or mimetypes.guess_type(path.name)[0]
                         or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- routing --------------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/" or path == "/index.html":
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            self._serve_file(WEB_DIR / path[len("/static/"):])
        elif path == "/api/materials":
            _json(self, [m.to_dict() for m in PIPE.store.list()])
        elif path == "/api/meta":
            from .models import LANGUAGES, REGION_MONTHLY_MIN_VIEWS
            _json(self, {"topics": TOPICS, "manual_checks": MANUAL_CHECK_ITEMS,
                         "provider": PIPE.provider.name,
                         "languages": LANGUAGES,
                         "region_monthly_min_views": REGION_MONTHLY_MIN_VIEWS,
                         "targets": CFG.get("languages", {}).get("targets", [])})
        elif path == "/api/queue":
            _json(self, [q.to_dict() for q in PIPE.store.list_queue()])
        elif path == "/api/candidates":
            _json(self, [c.to_dict() for c in PIPE.store.list_candidates()])
        elif path == "/api/patterns":
            _json(self, PIPE.store.list_patterns())
        elif path == "/api/analytics":
            _json(self, PIPE.analytics())
        elif path == "/api/settings":
            safe = {k: v for k, v in CFG.items()}
            _json(self, safe)
        elif path.startswith("/api/files/"):
            rel = path[len("/api/files/"):]
            target = (DATA / rel).resolve()
            if DATA.resolve() not in target.parents and target != DATA.resolve():
                self.send_error(403)
                return
            self._serve_file(target)
        else:
            self.send_error(404)

    def do_POST(self):
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        try:
            body = self._body()
            if parts == ["api", "materials", "regenerate"]:
                mat = PIPE.register_regenerated(
                    story_url=body.get("story_url", ""),
                    prompt=body.get("prompt", ""),
                    topic=body.get("topic", ""),
                    fact=body.get("fact", ""))
                _json(self, mat.to_dict(), 201)
                return
            if parts == ["api", "candidates"]:
                cand = PIPE.add_candidate(
                    topic=body.get("topic", ""), url=body.get("url", ""),
                    note=body.get("note", ""), origin_lang=body.get("origin_lang", ""))
                _json(self, cand.to_dict(), 201)
                return
            if len(parts) == 4 and parts[:2] == ["api", "queue"] and parts[3] == "result":
                item = PIPE.record_publish_result(
                    parts[2], status=body.get("status", ""),
                    post_url=body.get("post_url", ""), error=body.get("error", ""))
                _json(self, item.to_dict())
                return
            if len(parts) == 4 and parts[:2] == ["api", "candidates"]:
                cand = PIPE.set_candidate_status(parts[2], body.get("status", ""))
                _json(self, cand.to_dict())
                return
            if parts == ["api", "batch"]:
                _json(self, PIPE.batch(body.get("ids", []), body.get("action", "")))
                return
            if parts == ["api", "settings"]:
                _save_user_settings(body)
                _json(self, {"ok": True, "note": "user.json에 저장됨. "
                         "렌더·언어 설정은 즉시 반영, 프로바이더 변경은 재시작 필요"})
                return
            if parts == ["api", "materials"]:
                raw = base64.b64decode(body["data_base64"])
                ext = Path(body.get("filename", "image.jpg")).suffix or ".jpg"
                mat = PIPE.register(
                    image_bytes=raw, ext=ext, source=body.get("source", ""),
                    rights=body.get("rights", "불명확"),
                    topic=body.get("topic", ""), origin_lang=body.get("origin_lang", ""))
                _json(self, mat.to_dict(), 201)
                return
            if len(parts) == 5 and parts[:2] == ["api", "materials"] \
                    and parts[3] == "slides":
                _json(self, PIPE.generate_slide_image(
                    parts[2], int(parts[4])).to_dict())
                return
            if len(parts) >= 3 and parts[:2] == ["api", "materials"]:
                mid, action = parts[2], parts[3] if len(parts) > 3 else ""
                if action == "slides":
                    _json(self, PIPE.set_slides(
                        mid, body.get("slides", [])).to_dict())
                elif action == "analyze":
                    _json(self, PIPE.analyze(mid).to_dict())
                elif action == "fact":
                    _json(self, PIPE.set_fact(mid, body.get("fact", ""),
                                              body.get("visible_info")).to_dict())
                elif action == "copies":
                    _json(self, PIPE.generate_copies(
                        mid, humor=bool(body.get("humor"))).to_dict())
                elif action == "choose":
                    _json(self, PIPE.choose_copy(
                        mid, body.get("text", ""), body.get("highlight", "")).to_dict())
                elif action == "render":
                    _json(self, PIPE.render(mid).to_dict())
                elif action == "localize":
                    _json(self, PIPE.localize(mid, body.get("lang", "en")).to_dict())
                elif action == "localize_all":
                    _json(self, PIPE.localize_all(mid).to_dict())
                elif action == "review":
                    _json(self, PIPE.review(
                        mid, body.get("manual_checks", [])).to_dict())
                elif action == "export":
                    _json(self, PIPE.export(mid))
                elif action == "enqueue":
                    _json(self, PIPE.enqueue(mid).to_dict(), 201)
                elif action == "views":
                    _json(self, PIPE.record_views(
                        mid, int(body.get("views", 0)),
                        body.get("posted_at", "")).to_dict())
                else:
                    self.send_error(404)
                return
            self.send_error(404)
        except (ValueError, PermissionError) as exc:
            _json(self, {"error": str(exc)}, 400)
        except KeyError as exc:
            _json(self, {"error": str(exc)}, 404)
        except Exception as exc:  # surface, don't crash the server
            _json(self, {"error": f"{type(exc).__name__}: {exc}"}, 500)


_SETTINGS_KEYS = ("render", "languages", "copy")


def _save_user_settings(body: dict) -> None:
    """Persist personal overrides to config/user.json (private) and apply the
    live-updatable parts (render, languages, copy) to the running config."""
    user_path = ROOT / "config" / "user.json"
    existing = {}
    if user_path.exists():
        existing = json.loads(user_path.read_text(encoding="utf-8"))
    for key in _SETTINGS_KEYS:
        if key in body:
            existing[key] = body[key]
            CFG[key] = body[key]
    user_path.write_text(json.dumps(existing, ensure_ascii=False, indent=1),
                         encoding="utf-8")


def main():
    server_cfg = CFG.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = int(server_cfg.get("port", 8765))
    print(f"hiway-storyforge http://{host}:{port} (provider={PIPE.provider.name})")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
