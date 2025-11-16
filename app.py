# app.py
from flask import Flask, request, jsonify
import os
import base64
import io
from pydub import AudioSegment
import torch  # or tensorflow if using .h5
# import your_model  # <-- your trained model

app = Flask(__name__)

# Mock model (replace with real)
MODEL_LOADED = True
# model = torch.load('model.pt')  # <-- your actual model

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": MODEL_LOADED
    })

@app.route('/watermark', methods=['POST'])
def watermark():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"error": "Missing 'audio' in JSON"}), 400

        audio_b64 = data['audio']
        if 'base64,' in audio_b64:
            audio_b64 = audio_b64.split('base64,')[1]

        audio_data = base64.b64decode(audio_b64)
        audio = AudioSegment.from_file(io.BytesIO(audio_data))

        # === EMBED WATERMARK (example: add silence marker) ===
        silence = AudioSegment.silent(duration=100)  # 100ms marker
        watermarked = audio + silence

        # Export to WAV buffer
        buffer = io.BytesIO()
        watermarked.export(buffer, format="wav")
        buffer.seek(0)
        watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(buffer.read()).decode()}"

        # === DETECT WATERMARK (mock) ===
        has_watermark = len(audio) % 1000 < 500  # dummy logic

        return jsonify({
            "watermarked_audio": watermarked_b64,
            "has_watermark": has_watermark,
            "confidence": 0.98 if has_watermark else 0.12
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
