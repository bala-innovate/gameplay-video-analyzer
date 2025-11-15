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

    csv_file = request.files["file"]
    filename = request.form.get("filename") or csv_file.filename

    print("\n=== CSV RECEIVED ===")
    print(f"Filename: {filename}")
    process_from_app(filename)

    print(f"Received file: {filename}")
    # csv_bytes = csv_file.read()
    # csv_text = csv_bytes.decode("utf-8", errors="replace")

    # print("--- CSV Preview (first 10 lines) ---")
    # lines = csv_text.splitlines()
    # for line in lines[:10]:
    #     print(line)
    # print("=== END PREVIEW ===\n")

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

    print(f"Received file: {filename}")

    return jsonify({
        "ok": True,
        "filename": filename,
        "message": f"Received CSV '{filename}' and processed the huddle frames",
        "probs_by_players": probs_players, 
        "probs_by_time": probs_time,        
    })
if __name__ == '__main__':
    app.run()