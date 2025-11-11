from flask import Flask, request, jsonify
from flask_cors import CORS
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

    print(f"Received file: {filename}")
    csv_bytes = csv_file.read()
    csv_text = csv_bytes.decode("utf-8", errors="replace")

    print("\n=== CSV RECEIVED ===")
    print(f"Filename: {filename}")
    print("--- CSV Preview (first 10 lines) ---")
    lines = csv_text.splitlines()
    for line in lines[:10]:
        print(line)
    print("=== END PREVIEW ===\n")

    return jsonify({
        "ok": True,
        "filename": filename,
        "message": f"Received CSV '{filename}'",
    })
if __name__ == '__main__':
    app.run()