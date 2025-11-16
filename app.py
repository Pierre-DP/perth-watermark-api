from flask import Flask, request, jsonify
from perth import PerthImplicitWatermarker
import librosa
import soundfile as sf
import io
import base64
import torch
import os

app = Flask(__name__)

# Lazy load the watermarker
watermarker = None

def get_watermarker():
    global watermarker
    if watermarker is None:
        print("Loading Perth watermarker model...")
        watermarker = PerthImplicitWatermarker()
        print("Perth watermarker model loaded successfully")
    return watermarker

@app.route('/health', methods=['GET'])
def health():
    try:
        wm = get_watermarker()
        return jsonify({"status": "healthy", "model_loaded": True})
    except Exception as e:
        return jsonify({"status": "unhealthy", "model_loaded": False, "error": str(e)}), 500

@app.route('/watermark', methods=['POST'])
def watermark():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"error": "Missing 'audio' (base64)"}), 400

        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]

        watermark_id = data.get('watermark_id', 'PERTH-DEFAULT')

        # Decode and load audio
        audio_bytes = base64.b64decode(audio_b64)
        audio_data, sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)

        # Resample to 16kHz (Perth optimal)
        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            sr = 16000

        print(f"Watermarking audio: {len(audio_data)} samples @ {sr}Hz | ID: {watermark_id}")

        wm = get_watermarker()
        watermarked_audio = wm.apply_watermark(audio_data, sample_rate=sr, watermark=watermark_id)

        # Encode to base64 with data URI
        buffer = io.BytesIO()
        sf.write(buffer, watermarked_audio, sr, format='WAV')
        buffer.seek(0)
       watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "watermark_id": watermark_id
        })
    except Exception as e:
        print(f"Watermarking error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/detect', methods=['POST'])
def detect():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"error": "Missing 'audio' (base64)"}), 400

        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]

        # Decode and load
        audio_bytes = base64.b64decode(audio_b64)
        audio_data, sr = librosa.load(io.BytesIO(audio_bytes), sr=None, mono=True)

        # Resample to 16kHz
        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            sr = 16000

        print(f"Detecting watermark: {len(audio_data)} samples @ {sr}Hz")

        wm = get_watermarker()
        confidence = wm.get_watermark(audio_data, sample_rate=sr)
        confidence_percent = round(float(confidence) * 100, 2)
        detected = confidence > 0.5

        print(f"Detection: {'YES' if detected else 'NO'} | Confidence: {confidence_percent}%")

        return jsonify({
            "success": True,
            "detected": detected,
            "confidence": confidence_percent,
            "watermark_id": None  # Perth doesn't extract ID — use external tracking
        })
    except Exception as e:
        print(f"Detection error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
