from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import json
import shutil
import re

import warnings
warnings.filterwarnings("ignore")

from video_processor import process_from_app
app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

RESULTS_DIR = Path("results")
CACHE_DIR = RESULTS_DIR / "cache"
# Bump this when analysis/tracking output format changes so stale cache is ignored.
CACHE_VERSION = "v3_overlay_boxes_plus_heatmap"

RESULT_FILES = [
    "move_policy_by_defenderCount_bin.json",
    "move_policy_by_frameCountSincePlayStart_bin.json",
    "move_vs_defenders_events.csv",
    "move_vs_timeSinceDownFrameCount.csv",
    "tracked_video.mp4",
    "heatmap_video.mp4",
]


def _cache_key(schema_filename):
    stem = Path(schema_filename).stem
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]', '_', stem)
    return f"{CACHE_VERSION}_{safe_stem}"


def _get_cache(schema_filename):
    """Return the cache dir for this schema if ALL result files are present."""
    key = _cache_key(schema_filename)
    cache = CACHE_DIR / key
    if cache.is_dir() and all((cache / f).exists() for f in RESULT_FILES):
        return cache
    return None


def _save_cache(schema_filename):
    """Copy current results into a per-schema cache folder."""
    key = _cache_key(schema_filename)
    cache = CACHE_DIR / key
    cache.mkdir(parents=True, exist_ok=True)
    for f in RESULT_FILES:
        src = RESULTS_DIR / f
        if src.exists():
            shutil.copy2(src, cache / f)
    print(f"[Cache Saved] {cache}")


@app.post("/analyze")
def analyze():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No CSV uploaded"}), 400

    schema_file = request.files["file"]
    schema_filename = request.form.get("filename") or schema_file.filename

    # Save schema CSV → data/Annotations/actions/
    actions_dir = Path("data/Annotations/actions/NFL_Blitz")
    actions_dir.mkdir(parents=True, exist_ok=True)

    schema_path = actions_dir / schema_filename
    schema_file.save(schema_path)

    print(f"[Schema Saved] {schema_path}")
    start_times_file = request.files.get("start_times")
    start_times_name = None
    if start_times_file and start_times_file.filename:
        start_times_name = start_times_file.filename

        # Save start_times CSV → data/Annotations/starttime/
        starttime_dir = Path("data/Annotations/start_times/NFL_Blitz")
        starttime_dir.mkdir(parents=True, exist_ok=True)

        start_times_path = starttime_dir / start_times_name
        start_times_file.save(start_times_path)

        print(f"[StartTimes Saved] {start_times_path}")

    # --- Check cache ---
    cached = _get_cache(schema_filename)
    if cached:
        print(f"[Cache Hit] {cached}")
        with (cached / "move_policy_by_defenderCount_bin.json").open() as f:
            probs_players = json.load(f)
        with (cached / "move_policy_by_frameCountSincePlayStart_bin.json").open() as f:
            probs_time = json.load(f)

        cache_key = _cache_key(schema_filename)
        return jsonify({
            "ok": True,
            "cache_hit": True,
            "filename": schema_filename,
            "start_times_name": start_times_name,
            "message": f"Loaded cached results for '{schema_filename}'",
            "probs_by_players": probs_players,
            "probs_by_time": probs_time,
            "tracked_video_url": f"/results/cache/{cache_key}/tracked_video.mp4",
            "heatmap_video_url": f"/results/cache/{cache_key}/heatmap_video.mp4",
        })

    # --- No cache: run full analysis ---
    print(f"[Cache Miss] Running full analysis for '{schema_filename}'")
    process_from_app(schema_filename)

    path_players = RESULTS_DIR / "move_policy_by_defenderCount_bin.json"
    path_time = RESULTS_DIR / "move_policy_by_frameCountSincePlayStart_bin.json"

    if not path_players.exists():
        return jsonify({
            "ok": False,
            "error": f"Results file not found: {path_players}"
        }), 500

    if not path_time.exists():
        return jsonify({
            "ok": False,
            "error": f"Results file not found: {path_time}"
        }), 500

    with path_players.open("r", encoding="utf-8") as f:
        probs_players = json.load(f)

    with path_time.open("r", encoding="utf-8") as f:
        probs_time = json.load(f)

    _save_cache(schema_filename)

    return jsonify({
        "ok": True,
        "cache_hit": False,
        "filename": schema_filename,
        "start_times_name": start_times_name,
        "message": f"Processed CSV '{schema_filename}'",
        "probs_by_players": probs_players,
        "probs_by_time": probs_time,
        "tracked_video_url": "/results/tracked_video.mp4",
        "heatmap_video_url": "/results/heatmap_video.mp4",
    })


@app.route("/results/<path:filename>")
def serve_result(filename):
    return send_from_directory("results", filename)


if __name__ == '__main__':
    app.run()
