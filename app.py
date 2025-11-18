from flask import Flask, request, jsonify
import base64
import os
import subprocess
import tempfile
import io
from pydub import AudioSegment
import librosa
import soundfile as sf
import numpy as np
import torch
from perth import PerthImplicitWatermarker
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

app = Flask(__name__)

# Optional: Keep Perth for confidence fallback (not required for ID tracking)
torch.set_default_dtype(torch.float32)
torch.backends.cudnn.benchmark = False
perth_watermarker = None

def get_perth_watermarker():
    global perth_watermarker
    if perth_watermarker is None:
        try:
            print("Loading Perth watermarker (optional fallback)...")
            perth_watermarker = PerthImplicitWatermarker()
            print("Perth loaded")
        except Exception as e:
            print(f"Perth failed to load: {e}")
            from perth import DummyWatermarker
            perth_watermarker = DummyWatermarker()
    return perth_watermarker

@app.route('/health', methods=['GET'])
def health():
    try:
        # Test audiowmark binary
        result = subprocess.run(['audiowmark', '--version'], capture_output=True, text=True)
        audiowmark_ok = result.returncode == 0
        return jsonify({
            "status": "healthy",
            "audiowmark": audiowmark_ok,
            "audiowmark_version": result.stdout.strip() if audiowmark_ok else "not found",
            "perth_loaded": perth_watermarker is not None
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# =============================================================================
# 1. EMBED WATERMARK WITH UNIQUE ID (audiowmark) — This is your main flow
# =============================================================================
@app.route('/watermark', methods=['POST'])
def watermark():
    tmp_in = None

    tmp_out = None
    try:
        data = request.get_json()
        if not data or 'audio' not in data or 'watermark_id' not in data:
            return jsonify({"success": False, "error": "Missing 'audio' or 'watermark_id'"}), 400

        audio_b64 = data['audio']
        watermark_id = str(data['watermark_id'])  # e.g. "AD-BREAKFAST-001"

        # Decode base64
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        audio_bytes = base64.b64decode(audio_b64)

        # Write to temp input file
        tmp_in = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        with open(tmp_in, 'wb') as f:
            f.write(audio_bytes)

        # Output file
        tmp_out = tempfile.mktemp(suffix='_wm.wav')

        # Run audiowmark add
        result = subprocess.run(
            ['audiowmark', 'add', tmp_in, tmp_out, watermark_id],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"audiowmark failed: {result.stderr}")

        # Read watermarked file
        with open(tmp_out, 'rb') as f:
            watermarked_bytes = f.read()

        watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(watermarked_bytes).decode()}"

        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "watermark_id": watermark_id,
            "method": "audiowmark"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        for path in [tmp_in, tmp_out]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass


# =============================================================================
# 2. DETECT EXACT AD ID FROM LIVE STREAM CHUNK (audiowmark) — MAIN ENDPOINT
# =============================================================================
@app.route('/detect-id', methods=['POST'])
def detect_id():
    tmp_path = None
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio'"}), 400

        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        audio_bytes = base64.b64decode(audio_b64)

        # Save to secure temp file
        tmp_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        with open(tmp_path, 'wb') as f:
            f.write(audio_bytes)

        # Extract watermark ID
        result = subprocess.run(
            ['audiowmark', 'get', tmp_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            watermark_id = result.stdout.strip()
            return jsonify({
                "success": True,
                "detected": True,
                "watermark_id": watermark_id,
                "confidence": 100.0,
                "method": "audiowmark"
            })
        else:
            return jsonify({
                "success": True,
                "detected": False,
                "watermark_id": None,
                "confidence": 0.0,
                "method": "audiowmark"
            })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass


# =============================================================================
# 3. OPTIONAL: Perth confidence detection (fallback or hybrid)
# =============================================================================
@app.route('/detect-perth', methods=['POST'])
def detect_perth():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio'"}), 400

        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            mime = audio_b64.split(';')[0]
            audio_b64 = audio_b64.split(',', 1)[1]
        else:
            mime = 'audio/wav'

        audio_bytes = base64.b64decode(audio_b64)

        # Convert via pydub
        if 'mpeg' in mime or 'mp3' in mime:
            audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        elif 'aac' in mime:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format='aac')
        else:
            audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))

        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format='wav')
        wav_buffer.seek(0)

        audio_data, sr = librosa.load(wav_buffer, sr=None, mono=True, dtype=np.float32)
        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)

        wm = get_perth_watermarker()
        with torch.no_grad():
            confidence = wm.get_watermark(audio_data, sample_rate=16000)

        confidence_pct = round(float(confidence) * 100, 2)

        return jsonify({
            "success": True,
            "detected": confidence > 0.5,
            "confidence": confidence_pct,
            "method": "perth"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
