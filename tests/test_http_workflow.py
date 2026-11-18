"""Exercise the same JSON routes as the workbench and external operator."""
import io
import json
import os
import subprocess
import sys
from threading import Thread
from urllib.request import Request, urlopen
from zipfile import ZipFile

from PIL import Image


def test_demo_to_confirmed_due_item_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("PB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PB_PROVIDER", "stub")
    from storyforge import web

    env = {**os.environ, "PYTHONPATH": str(web.ROOT / "src")}
    for _ in range(2):
        subprocess.run([sys.executable, "scripts/seed_demo.py"], check=True, env=env)
    server = web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def api(path, body=None):
        payload = None if body is None else json.dumps(body).encode()
        with urlopen(Request(base + path, data=payload,
                             headers={"Content-Type": "application/json"}), timeout=15) as response:
            return json.load(response)

    try:
        material, = api("/api/materials")
        route = "/api/materials/" + material["id"] + "/"
        meta = api("/api/meta")
        api(route + "choose", {"text": material["fact"], "original_ratio": True})
        api(route + "render", {})
        api(route + "review", {"manual_checks": meta["manual_checks"]})
        package = api(route + "export", {})
        with urlopen(base + "/api/files/" + package["zip"]) as response:
            with ZipFile(io.BytesIO(response.read())) as archive:
                assert archive.testzip() is None
                image_name, = json.loads(archive.read("meta.json"))["post_files"]
                with Image.open(io.BytesIO(archive.read(image_name))) as image:
                    assert image.size == (1080, 1080)
        item = api(route + "enqueue", {"on_date": "2020-01-01"})
        result_route = "/api/queue/" + item["id"]
        assert api(result_route + "/confirm", {})["status"] == "컨펌됨"
        property_queue = tmp_path / "property.json"
        property_queue.write_text('{"items":[]}')
        due = subprocess.check_output([sys.executable, "scripts/check_due.py", "--animal-queue",
                                      str(tmp_path / "queue.json"), "--property-queue", str(property_queue)])
        assert json.loads(due)["due_confirmed"][0]["id"] == item["id"]
        api(result_route + "/result", {"status": "게시완료", "post_id": "sample",
                                      "post_url": "https://example.com/post"})
        api(route + "views", {"views": 123})
        assert api("/api/analytics")["total_views"] == 123
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
