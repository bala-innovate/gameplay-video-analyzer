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
    csv_bytes = request.data or b""
    csv_text = csv_bytes.decode("utf-8", errors="replace")
    print("\n=== RECEIVED CSV PREVIEW ===")
    print(csv_text[:300])
    print("=== END PREVIEW ===\n")
    return jsonify({
        "ok": True,
        "bytes": len(csv_bytes),
        "message": "Received CSV. Backend connected.",
    })
if __name__ == '__main__':
    app.run()