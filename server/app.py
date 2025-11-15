from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import json

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


@app.post("/analyze")
def analyze():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No CSV uploaded"}), 400

    schema_file = request.files["file"]
    schema_filename = request.form.get("filename") or schema_file.filename

    # Save schema CSV → data/Annotations/actions/
    actions_dir = Path("data/Annotations/actions")
    actions_dir.mkdir(parents=True, exist_ok=True)

    schema_path = actions_dir / schema_filename
    schema_file.save(schema_path)

    print(f"[Schema Saved] {schema_path}")
    start_times_file = request.files.get("start_times")
    start_times_name = None
    start_times_path = None

    if start_times_file and start_times_file.filename:
        start_times_name = start_times_file.filename

        # Save start_times CSV → data/Annotations/starttime/
        starttime_dir = Path("data/Annotations/start_times")
        starttime_dir.mkdir(parents=True, exist_ok=True)

        start_times_path = starttime_dir / start_times_name
        start_times_file.save(start_times_path)

        print(f"[StartTimes Saved] {start_times_path}")

    # print("\n=== CSV RECEIVED ===")
    # print(f"Filename: {filename}")
    

    # print(f"Received file: {filename}")

    
    # csv_bytes = csv_file.read()
    # csv_text = csv_bytes.decode("utf-8", errors="replace")

    # print("--- CSV Preview (first 10 lines) ---")
    # lines = csv_text.splitlines()
    # for line in lines[:10]:
    #     print(line)
    # print("=== END PREVIEW ===\n")

    process_from_app(schema_filename)


    path_players = Path("results") / "move_policy_by_defenderCount_bin.json"
    path_time = Path("results") / "move_policy_by_frameCountSincePlayStart_bin.json"

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


    return jsonify({
        "ok": True,
        "filename": schema_filename,
        "start_times_name": start_times_name,
        "message": f"Processed CSV '{schema_filename}'",
        "probs_by_players": probs_players,
        "probs_by_time": probs_time
    })
if __name__ == '__main__':
    app.run()