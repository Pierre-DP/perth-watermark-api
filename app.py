from flask import Flask, request, jsonify
import perth
import librosa
import soundfile as sf
import io
import base64
import torch
import os

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "model_loaded": True})

@app.route('/watermark', methods=['POST'])
def watermark():
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
            return jsonify({"error": "Missing 'audio' (base64)"}), 400

        audio_b64 = data['audio']
        message = data.get('watermark_id', 'PERTH-DEFAULT')  # Custom message

        # Decode base64 to audio tensor
        audio_bytes = base64.b64decode(audio_b64.split(',')[1] if ',' in audio_b64 else audio_b64)
        audio_data, sr = librosa.load(io.BytesIO(audio_bytes), sr=None)

        # Initialize Perth neural watermarker
        watermarker = perth.PerthImplicitWatermarker()

        # Embed watermark
        watermarked_audio = watermarker.apply_watermark(audio_data, sample_rate=sr, watermark=message)

        # Detect watermark (confidence: 1.0 = fully detected)
        confidence = watermarker.get_watermark(watermarked_audio, sample_rate=sr)

        # Encode watermarked audio back to base64
        buffer = io.BytesIO()
        sf.write(buffer, watermarked_audio, sr)
        watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(buffer.getvalue()).decode()}"

        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "has_watermark": confidence > 0.5,
            "confidence": float(confidence),
            "message": message
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
