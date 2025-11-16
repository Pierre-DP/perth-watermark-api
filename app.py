# app.py
from flask import Flask, request, jsonify
import librosa
import soundfile as sf
import io
import base64
import os
import numpy as np
import torch
import warnings

# Suppress pkg_resources deprecation warning (Perth bug)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

# Correct Perth import + fallback
try:
    from perth.perth_net.perth_net_implicit.perth_watermarker import PerthImplicitWatermarker
    from perth import DummyWatermarker
    PERTH_AVAILABLE = True
except Exception as e:
    print(f"Perth neural import failed: {e} — using dummy fallback")
    from perth import DummyWatermarker
    PERTH_AVAILABLE = False

app = Flask(__name__)

# Force CPU for Railway free tier
os.environ['CUDA_VISIBLE_DEVICES'] = ''
torch.set_default_dtype(torch.float32)
torch.backends.cudnn.benchmark = False

# === Lazy-load watermarker ===
watermarker = None


def get_watermarker():
    global watermarker
    if watermarker is None:
        try:
            if PERTH_AVAILABLE:
                print("Loading Perth neural watermarker (CPU mode)...")
                watermarker = PerthImplicitWatermarker(device=None)
                print("Neural watermarker loaded successfully")
            else:
                raise ImportError("Neural Perth not available")
        except Exception as e:
            print(f"Neural load failed ({e}) — using dummy fallback")
            watermarker = DummyWatermarker()
    return watermarker


@app.route('/health', methods=['GET'])
def health():
    try:
        wm = get_watermarker()
        model_type = "neural" if PERTH_AVAILABLE and isinstance(wm, PerthImplicitWatermarker) else "dummy"
        return jsonify({"status": "healthy", "model_loaded": True, "type": model_type})
    except Exception as e:
        return jsonify({"status": "unhealthy", "model_loaded": False, "error": str(e)}), 500


@app.route('/watermark', methods=['POST'])
def watermark():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio' (base64)"}), 400

        audio_b64 = data['audio']
        watermark_id = data.get('watermark_id', 'PERTH-DEFAULT')

        # Strip data URI prefix
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]

        audio_bytes = base64.b64decode(audio_b64)

        buffer = io.BytesIO(audio_bytes)
        buffer.seek(0)
        audio_data, sr = librosa.load(buffer, sr=None, mono=True, dtype=np.float32)

        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            sr = 16000

        print(f"Watermarking audio: {len(audio_data)} samples @ {sr}Hz | ID: {watermark_id}")

        wm = get_watermarker()
        with torch.no_grad():
            watermarked_audio = wm.apply_watermark(audio_data, sample_rate=sr, watermark=watermark_id)

        out_buffer = io.BytesIO()
        sf.write(out_buffer, watermarked_audio, sr, format='WAV')
        out_buffer.seek(0)
        watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(out_buffer.getvalue()).decode()}"

        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "watermark_id": watermark_id
        })
    except Exception as e:
        print(f"Watermarking error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Watermark failed: {str(e)}"}), 500


@app.route('/detect', methods=['POST'])
def detect():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio' (base64)"}), 400

        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]

        audio_bytes = base64.b64decode(audio_b64)

        buffer = io.BytesIO(audio_bytes)
        buffer.seek(0)
        audio_data, sr = librosa.load(buffer, sr=None, mono=True, dtype=np.float32)

        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            sr = 16000

        print(f"Detecting watermark: {len(audio_data)} samples @ {sr}Hz")

        wm = get_watermarker()
        with torch.no_grad():
            confidence = wm.get_watermark(audio_data, sample_rate=sr)
        confidence_percent = round(float(confidence) * 100, 2)
        detected = confidence > 0.5

        # === FIX: Ensure bool is JSON serializable ===
        detected_json = bool(detected)

        print(f"Detection: {'YES' if detected else 'NO'} | Confidence: {confidence_percent}%")

        return jsonify({
            "success": True,
            "detected": detected_json,
            "confidence": confidence_percent,
            "watermark_id": None
        })
    except Exception as e:
        print(f"Detection error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Detection failed: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
