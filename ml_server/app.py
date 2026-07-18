"""
LeafScan ML Server — Flask + TensorFlow + MySQL
-------------------------------------------------
Runs on http://localhost:5000

Endpoints:
  POST /register          — create account
  POST /login             — sign in, returns user_id
  POST /analyze           — run TF inference + save to DB
  GET  /history/<user_id> — get past scans
  GET  /stats/<user_id>   — dashboard stats
  GET  /health            — server status
"""

import hashlib
import io
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS

from predictor import PlantDiseasePredictor
from disease_db import DISEASE_DATABASE, SUPPORTED_PLANTS
from database import init_database, register_user, login_user, save_scan, get_user_history, get_user_stats

app = Flask(__name__)
CORS(app)

try:
    init_database()
    print("[LeafScan] MySQL connected and leafscan schema is ready")
except Exception as exc:
    print(f"[LeafScan] MySQL startup check failed: {exc}")

# Load TF model once at startup
predictor = PlantDiseasePredictor()

INVALID_LEAF_MESSAGE = "Please upload the correct image. Only clear green leaf photos are supported."
CLEAR_PHOTO_MESSAGE = "Photo is not clear please upload the appropriate image."
MIN_SHARPNESS_SCORE = 150.0


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def is_clear_photo(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((224, 224))
        arr = np.asarray(img, dtype=np.float32)
        laplacian = (
            -4 * arr[1:-1, 1:-1] +
            arr[:-2, 1:-1] +
            arr[2:, 1:-1] +
            arr[1:-1, :-2] +
            arr[1:-1, 2:]
        )
        sharpness = float(laplacian.var())
        if sharpness < MIN_SHARPNESS_SCORE:
            print(f"[is_clear_photo] REJECTED: blurry sharpness={sharpness:.1f}")
            return False
        return True
    except Exception as e:
        print(f"[is_clear_photo] ERROR: {e}")
        return False


def is_plant_image(image_bytes):
    """
    Plant image validator — logs why it rejects so we can debug.
    Very lenient: only blocks obvious non-plant images.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((100, 100))
        arr = np.array(img, dtype=np.float32).astype(np.int32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        total = 100 * 100

        reasons = []

        # ── 1. Flat/solid screenshots ──────────────────────────────────
        if arr.std() < 15:
            reasons.append(f"flat_image std={arr.std():.1f}")

        # ── 2. Skin tones (human/animal) ───────────────────────────────────
        # Much higher threshold (>0.20) to avoid false positives on brown
        # necrotic spots / disease damage that appear on plant leaves.
        skin = np.sum(
            (r > 90) & (g > 35) & (b > 20) &
            (r > g) & (r > b) &
            (np.abs(r - g) > 12)
        )
        if skin / total > 0.50:
            reasons.append(f"skin_detected {skin/total:.3f}")

        # ── 3. Heavy blue sky ──────────────────────────────────────────
        blue = np.sum((b > r + 25) & (b > g + 20) & (b > 100))
        if blue / total > 0.45:
            reasons.append(f"blue_sky {blue/total:.3f}")

        # ── 4. Pure white/grey background ─────────────────────────────
        brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3
        white_bg = np.sum(
            (brightness > 215) &
            (np.abs(r - g) < 10) &
            (np.abs(g - b) < 10)
        )
        if white_bg / total > 0.70:
            reasons.append(f"white_bg {white_bg/total:.3f}")

        # ── 5. Green pixel content ──────────────────────────────────────
        green_ish = np.sum((g >= r * 0.90) & (g >= b * 0.90) & (g > 25))
        if green_ish / total < 0.015:
            reasons.append(f"low_green {green_ish/total:.4f}")

        if reasons:
            print(f"[is_plant_image] REJECTED: {', '.join(reasons)}")

        return len(reasons) == 0
    except Exception as e:
        print(f"[is_plant_image] ERROR: {e}")
        return False


def has_clear_green_leaf(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((160, 160))
        arr = np.array(img, dtype=np.float32).astype(np.int32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        total = 160 * 160
        reasons = []

        if arr.std() < 15:
            reasons.append(f"flat_image std={arr.std():.1f}")

        skin = np.sum(
            (r > 90) & (g > 35) & (b > 20) &
            (r > g) & (r > b) &
            (np.abs(r - g) > 12)
        )
        if skin / total > 0.50:
            reasons.append(f"skin_detected {skin/total:.3f}")

        blue = np.sum((b > r + 25) & (b > g + 20) & (b > 100))
        if blue / total > 0.45:
            reasons.append(f"blue_sky {blue/total:.3f}")

        brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3
        white_bg = np.sum(
            (brightness > 215) &
            (np.abs(r - g) < 10) &
            (np.abs(g - b) < 10)
        )
        if white_bg / total > 0.70:
            reasons.append(f"white_bg {white_bg/total:.3f}")

        max_channel = np.maximum(np.maximum(r, g), b)
        min_channel = np.minimum(np.minimum(r, g), b)
        saturation = (max_channel - min_channel) / np.maximum(max_channel, 1)

        strong_green = (
            (g > 35) &
            (g >= r * 1.04) &
            (g >= b * 1.04) &
            (saturation > 0.10) &
            (brightness > 28) &
            (brightness < 245)
        )
        leaf_green = (
            (g > 35) &
            (g >= r * 0.88) &
            (g >= b * 0.95) &
            (saturation > 0.08) &
            (brightness > 28) &
            (brightness < 235)
        )

        strong_green_ratio = np.sum(strong_green) / total
        leaf_green_ratio = np.sum(leaf_green) / total
        green_blocks = leaf_green.reshape(16, 10, 16, 10).mean(axis=(1, 3))
        biggest_green_block = float(green_blocks.max())

        if strong_green_ratio < 0.025 and leaf_green_ratio < 0.055:
            reasons.append(
                f"low_leaf_green strong={strong_green_ratio:.3f} leaf={leaf_green_ratio:.3f}"
            )
        if biggest_green_block < 0.08:
            reasons.append(f"no_clear_green_leaf_region block={biggest_green_block:.3f}")

        if reasons:
            print(f"[has_clear_green_leaf] REJECTED: {', '.join(reasons)}")

        return len(reasons) == 0
    except Exception as e:
        print(f"[has_clear_green_leaf] ERROR: {e}")
        return False


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not all(k in data for k in ["first_name", "last_name", "email", "password"]):
        return jsonify({"error": "first_name, last_name, email and password required"}), 400

    result = register_user(
        data["first_name"], data["last_name"],
        data["email"], hash_password(data["password"])
    )
    if result["success"]:
        return jsonify({"success": True, "user_id": result["user_id"]})
    return jsonify({"error": result["error"]}), 409


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not all(k in data for k in ["email", "password"]):
        return jsonify({"error": "email and password required"}), 400

    user = login_user(data["email"], hash_password(data["password"]))
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"error": "Invalid email or password"}), 401


# ── AI Analysis ────────────────────────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image field in request"}), 400

    image_file = request.files["image"]
    if not image_file.filename:
        return jsonify({"error": "Empty filename"}), 400

    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "Empty image file"}), 400

    if not is_clear_photo(image_bytes):
        return jsonify({"error": CLEAR_PHOTO_MESSAGE}), 400

    # Reject non-plant images before running TF inference
    if not has_clear_green_leaf(image_bytes):
        return jsonify({"error": INVALID_LEAF_MESSAGE}), 400
        return jsonify({"error": "Invalid image — please upload a plant or leaf photo only."}), 400

    # Run model inference
    try:
        raw_preds = predictor.predict(image_bytes, top_k=12)
    except Exception as e:
        return jsonify({"error": f"Inference failed: {str(e)}"}), 500

    if not raw_preds:
        return jsonify({
            "error": "Unsupported plant image. Please upload one of the supported plants only.",
            "supported_plants": SUPPORTED_PLANTS,
        }), 422

    # Enrich predictions with disease knowledge
    results = []
    top_info = DISEASE_DATABASE.get(raw_preds[0]["class"], {})
    top_plant = top_info.get("plant")
    for pred in raw_preds:
        label = pred["class"]
        info  = DISEASE_DATABASE.get(label, {})
        if top_plant and info.get("plant") != top_plant:
            continue
        results.append({
            "class":        label,
            "probability":  round(pred["probability"], 4),
            "confidence_pct": round(pred.get("similarity", pred["probability"]) * 100, 1),
            "similarity":   round(pred.get("similarity", 0), 4),
            "display_name": info.get("display_name", label),
            "plant":        info.get("plant", "Unknown"),
            "cause":        info.get("cause", "Unknown"),
            "severity":     info.get("severity", "Unknown"),
            "severity_pct": info.get("severity_pct", 50),
            "status_color": info.get("status_color", "warning"),
            "symptoms":     info.get("symptoms", []),
            "treatment":    info.get("treatment", []),
            "prevention":   info.get("prevention", []),
        })
        if len(results) >= 5:
            break

    response = {
        "top": results[0] if results else None,
        "predictions": results,
        "model": getattr(predictor, "backend", "PlantVillage classifier"),
        "supported_plants": SUPPORTED_PLANTS,
    }

    # Save to MySQL. If no logged-in user_id is provided, save under Guest User.
    user_id = request.form.get("user_id")
    if results:
        try:
            top = results[0]
            pred_id = save_scan(
                user_id,
                image_file.filename,
                top.get("display_name", ""),
                top.get("confidence_pct", 0),
            )
            response["prediction_id"] = pred_id
        except Exception as e:
            response["db_warning"] = str(e)

    return jsonify(response)


# ── History & Stats ────────────────────────────────────────────────────────────

@app.route("/history/<int:user_id>", methods=["GET"])
def history(user_id):
    return jsonify({"scans": get_user_history(user_id)})


@app.route("/stats/<int:user_id>", methods=["GET"])
def stats(user_id):
    return jsonify(get_user_stats(user_id))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": getattr(predictor, "backend", "PlantVillage classifier"),
        "classes": len(DISEASE_DATABASE),
        "supported_plants": SUPPORTED_PLANTS,
    })


if __name__ == "__main__":
    print("\nLeafScan ML Server starting on http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
