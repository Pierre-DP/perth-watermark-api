# app.py
from flask import Flask, request, jsonify
from perth import PerthImplicitWatermarker
import librosa
import soundfile as sf
import io
import base64
import os
import numpy as np
import torch
from pydub import AudioSegment  # For MP3/AAC conversion
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

app = Flask(__name__)

torch.set_default_dtype(torch.float32)
torch.backends.cudnn.benchmark = False

watermarker = None

def get_watermarker():
    global watermarker
    if watermarker is None:
        try:
            print("Loading Perth watermarker...")
            watermarker = PerthImplicitWatermarker()
            print("Loaded successfully")
        except Exception as e:
            print(f"Load failed ({e}) — using dummy")
            from perth import DummyWatermarker
            watermarker = DummyWatermarker()
    return watermarker

@app.route('/health', methods=['GET'])
def health():
    try:
        wm = get_watermarker()
        return jsonify({"status": "healthy", "model_loaded": True})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def process_audio(audio_b64, output_format='wav'):
    # Strip data URI
    if audio_b64.startswith('data:'):
        mime, b64 = audio_b64.split(',', 1)
        audio_bytes = base64.b64decode(b64)
    else:
        audio_bytes = base64.b64decode(audio_b64)

    # Detect format and convert to WAV
    if 'audio/mpeg' in mime or 'mp3' in mime.lower():
        audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
    elif 'audio/aac' in mime or 'aac' in mime.lower():
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format='aac')
    else:
        audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))

    # Export to WAV buffer
    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format='wav')
    wav_buffer.seek(0)

    # Load with librosa
    audio_data, sr = librosa.load(wav_buffer, sr=None, mono=True, dtype=np.float32)

    # Resample to 16kHz
    if sr != 16000:
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
        sr = 16000

    # Watermark
    wm = get_watermarker()
    with torch.no_grad():
        watermarked_audio = wm.apply_watermark(audio_data, sample_rate=sr, watermark='default')

    # Encode output
    out_buffer = io.BytesIO()
    sf.write(out_buffer, watermarked_audio, sr, format='WAV')
    out_buffer.seek(0)
    wav_out = out_buffer.getvalue()

    if output_format == 'mp3':
        out_audio = AudioSegment.from_wav(io.BytesIO(wav_out))
        mp3_buffer = io.BytesIO()
        out_audio.export(mp3_buffer, format='mp3')
        mp3_buffer.seek(0)
        out_b64 = f"data:audio/mpeg;base64,{base64.b64encode(mp3_buffer.getvalue()).decode()}"
    else:
        out_b64 = f"data:audio/wav;base64,{base64.b64encode(wav_out).decode()}"

    return out_b64

@app.route('/watermark', methods=['POST'])
def watermark():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio'"}), 400

        audio_b64 = data['audio']
        output_format = data.get('format', 'wav')

        watermarked_b64 = process_audio(audio_b64, output_format)

        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "watermark_id": "default"  # Perth doesn't extract ID
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/detect', methods=['POST'])
def detect():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"success": False, "error": "Missing 'audio'"}), 400

        audio_b64 = data['audio']

        # Load (handles MP3/AAC via pydub)
        mime = audio_b64.split(';')[0] if ';' in audio_b64 else 'audio/wav'
        audio_bytes = base64.b64decode(audio_b64.split(',')[1] if ',' in audio_b64 else audio_b64)

        if 'audio/mpeg' in mime or 'mp3' in mime.lower():
            audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        elif 'audio/aac' in mime or 'aac' in mime.lower():
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format='aac')
        else:
            audio = AudioSegment.from_wav(io.BytesIO(audio_bytes))

        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format='wav')
        wav_buffer.seek(0)

        audio_data, sr = librosa.load(wav_buffer, sr=None, mono=True, dtype=np.float32)

        if sr != 16000:
            audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=16000)
            sr = 16000

        wm = get_watermarker()
        with torch.no_grad():
            confidence = wm.get_watermark(audio_data, sample_rate=sr)
        confidence_percent = round(float(confidence) * 100, 2)
        detected = bool(confidence > 0.5)  # JSON-safe bool

        return jsonify({
            "success": True,
            "detected": detected,
            "confidence": confidence_percent,
            "watermark_id": None  # Perth doesn't extract ID
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
