"""Prepare and package EchoWorld's browser-only Pygbag frontend."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_BUILD = ROOT / "web_build"
WEB_DIST = ROOT / "web_dist"
SAFE_FRONTEND_FILES = (
    "game_app.py",
    "pixel_assets.py",
    "tutorial_system.py",
    "backend_adapter.py",
    "web_backend_client.py",
)


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != ROOT.resolve() and resolved.parent != WEB_BUILD.resolve():
        raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
    if resolved.is_dir():
        shutil.rmtree(resolved)


def prepare_frontend() -> None:
    WEB_BUILD.mkdir(parents=True, exist_ok=True)
    for filename in SAFE_FRONTEND_FILES:
        source = ROOT / filename
        if not source.is_file():
            raise FileNotFoundError(f"Missing browser frontend file: {source}")
        shutil.copy2(source, WEB_BUILD / filename)
        print(f"[web-build] copied {filename}")


def _find_bundle_root() -> Path:
    build_root = WEB_BUILD / "build"
    candidates = (
        build_root / "web",
        build_root,
    )
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    for index_file in build_root.rglob("index.html") if build_root.exists() else ():
        return index_file.parent
    raise RuntimeError("Pygbag completed but no generated index.html was found.")


def _inject_fullscreen_shell(index_file: Path) -> None:
    html = index_file.read_text(encoding="utf-8")
    style = """
<style id="echoworld-host-style">
html, body { width:100%; height:100%; margin:0!important; padding:0!important;
  overflow:hidden!important; background:#05080d!important; }
body { display:block!important; }
#canvas { position:fixed!important; inset:0!important; display:block!important;
  width:100vw!important; height:100vh!important; max-width:none!important;
  max-height:none!important; margin:0!important; padding:0!important;
  background:#05080d!important; image-rendering:auto!important; }
#canvas3d { background:#05080d!important; }
#transfer, #infobox { background:#05080d!important; color:#eafffb!important; }
#echoworld-fullscreen { position:fixed; right:14px; bottom:14px; z-index:99999;
  border:2px solid #72e6d1; background:#091820; color:#eafffb; padding:9px 13px;
  font:700 14px monospace; cursor:pointer; }
</style>
"""
    script = """
<button id="echoworld-fullscreen" type="button">Enter Fullscreen</button>
<script>
(() => {
  const button = document.getElementById('echoworld-fullscreen');
  button.addEventListener('click', async () => {
    const canvas = document.getElementById('canvas');
    try { await (canvas || document.documentElement).requestFullscreen(); } catch (_) {}
  });
  document.addEventListener('fullscreenchange', () => {
    button.style.display = document.fullscreenElement ? 'none' : 'block';
    window.dispatchEvent(new Event('resize'));
  });
  window.addEventListener('resize', () => {
    const canvas = document.getElementById('canvas');
    if (canvas) canvas.style.background = '#05080d';
  });
})();
</script>
"""
    if "echoworld-host-style" not in html:
        html = html.replace("</head>", f"{style}</head>")
    if 'id="echoworld-fullscreen"' not in html:
        html = html.replace("</body>", f"{script}</body>")
    index_file.write_text(html, encoding="utf-8")


def build_web() -> None:
    prepare_frontend()
    _safe_remove_tree(WEB_DIST)
    _safe_remove_tree(WEB_BUILD / "build")
    # EchoWorld has no startup audio, so do not gate Python execution behind
    # Pygbag's media-engagement prompt. The game title screen remains the
    # deliberate user-controlled start point.
    command = [
        sys.executable,
        "-m",
        "pygbag",
        "--build",
        "--ume_block",
        "0",
        str(WEB_BUILD),
    ]
    print("[web-build]", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)
    bundle_root = _find_bundle_root()
    shutil.copytree(bundle_root, WEB_DIST)
    _inject_fullscreen_shell(WEB_DIST / "index.html")
    print(f"[web-build] Browser bundle ready: {WEB_DIST}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Copy safe frontend modules without producing web_dist.",
    )
    args = parser.parse_args()
    if args.prepare_only:
        prepare_frontend()
        print(f"[web-build] Pygbag source prepared: {WEB_BUILD}")
    else:
        build_web()


if __name__ == "__main__":
    main()
