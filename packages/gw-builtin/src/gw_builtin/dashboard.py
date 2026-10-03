"""Open the known local dashboard without sending its credential through a model."""
from __future__ import annotations
import os
import pathlib
import subprocess
import sys
import time
import urllib.request
import webbrowser


def open_dashboard(home, project, client, config, *, port=7789):
    from .plugins import trace_repository
    with trace_repository(home, config):
        pass  # Register source owners before the independent dashboard opens.
    c = config["plugins"]["observe"]
    directory = pathlib.Path(c["options"].get("directory", str(home / "observability")))
    token_file = directory / "dashboard-token"
    url = "http://127.0.0.1:" + str(port)
    def ready():
        if not token_file.is_file() or token_file.is_symlink():
            return False
        try:
            token = token_file.read_text().strip()
            request = urllib.request.Request(url + "/api/runs", headers={"Authorization": "Bearer " + token})
            # A loopback request must not go through environment-configured HTTP proxies.
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=.5) as response:
                return response.status == 200
        except (OSError, ValueError):
            return False
    process = None
    if not ready():
        argv = [sys.executable, "-m", "gw_supervisor", "--home", str(home), "trace", "--project", str(project),
                "--client", client, "serve", "--port", str(port)]
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                  "start_new_session": os.name != "nt"}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(argv, **kwargs)
        for _ in range(40):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError("Dashboard could not start; port may be occupied")
            time.sleep(.1)
        else:
            process.terminate()
            raise RuntimeError("Dashboard did not become ready; no browser was opened")
    opened = webbrowser.open(url + "/#token=" + token_file.read_text().strip())
    return {"url": url + "/", "browser_opened": bool(opened), "started": process is not None,
            "pid": process.pid if process else None, "credential_returned": False,
            "note": "Dashboard runs on the agent's machine; remote/headless hosts may not open your desktop browser."}
