import sys
from unittest.mock import patch

import pytest

from scripts import safe_publish


@pytest.mark.parametrize("payload", ['{}', '{"posts": null}', '{"posts": [{}]}'])
def test_unreadable_inventory_prevents_publish(tmp_path, payload):
    media = tmp_path / "image.jpg"
    media.touch()
    with patch.object(sys, "argv", ["publish", "--account-id", "fixture",
                                   "--file", str(media), "--caption", "test"]), \
         patch.object(safe_publish, "run_cli", return_value=(0, payload, "")) as cli:
        assert safe_publish.main() == 1
        assert [call.args[0][0] for call in cli.call_args_list] == ["posts"]


@pytest.mark.parametrize(("mode", "code", "writes"), [
    ("new", 0, 1),
    ("existing", 2, 0),
    ("ambiguous", 2, 1),
])
def test_muse_cli_protocol_at_process_boundary(tmp_path, mode, code, writes):
    import json
    import os
    import subprocess

    cli = tmp_path / "instagram-cli"
    cli.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
state = Path(os.environ["PUBLISH_FIXTURE"])
with (state / "calls").open("a") as output:
    print(json.dumps(args), file=output)
assert args[args.index("--account-id") + 1] == "fixture"
if args[0] == "posts":
    assert args[args.index("--limit") + 1] == "20"
    posts = json.loads((state / "posts").read_text())
    print(json.dumps({"posts": posts}))
elif args[0] == "post-feed":
    assert args[args.index("--retries") + 1] == "0"
    caption = args[args.index("--caption") + 1]
    record = {"post_id": "fixture-id", "url": "https://example.com/test", "post_caption": caption}
    (state / "posts").write_text(json.dumps([record]))
    if os.environ["PUBLISH_MODE"] == "ambiguous":
        sys.exit(1)
    print(json.dumps(record))
else:
    sys.exit(1)
""")
    cli.chmod(0o755)
    caption = "테스트 캡션"
    posts = [{"post_caption": caption, "url": "https://example.com/test",
              "post_id": "fixture-id"}] if mode == "existing" else []
    (tmp_path / "posts").write_text(json.dumps(posts))
    media = tmp_path / "fixture.jpg"
    media.touch()
    proc = subprocess.run(
        [sys.executable, safe_publish.__file__, "--account-id", "fixture",
         "--caption", caption, "--file", str(media)],
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
             "PUBLISH_FIXTURE": str(tmp_path), "PUBLISH_MODE": mode},
        capture_output=True, text=True, check=False)
    assert proc.returncode == code, proc.stderr
    assert json.loads(proc.stdout)["url"] == "https://example.com/test"
    calls = [json.loads(line)[0] for line in (tmp_path / "calls").read_text().splitlines()]
    assert calls.count("post-feed") == writes


def test_timeout_without_receipt_needs_reconciliation(tmp_path, capsys):
    import json
    import subprocess

    media = tmp_path / "test.jpg"
    media.touch()
    empty = subprocess.CompletedProcess([], 0, '{"posts":[]}', '')
    with patch.object(sys, "argv", ["publish", "--account-id", "fixture", "--file",
                                   str(media), "--caption", "fixture"]), \
         patch.object(subprocess, "run", side_effect=[
             empty, subprocess.TimeoutExpired("post-feed", 1), empty]) as calls:
        assert safe_publish.main() == 1
        assert json.loads(capsys.readouterr().out)["needs_reconciliation"]
        assert [c.args[0][1] for c in calls.call_args_list] == ["posts", "post-feed", "posts"]
