# Add to your existing app.py
import subprocess
import json

@app.route('/detect-id', methods=['POST'])
def detect_id():
    try:
        data = request.get_json()
        audio_b64 = data['audio']
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        audio_bytes = base64.b64decode(audio_b64)

        # Save to temp WAV
        with open('/tmp/chunk.wav', 'wb') as f:
            f.write(audio_bytes)

        # Run audiowmark extract
        result = subprocess.run([
            'audiowmark', 'get', '/tmp/chunk.wav'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            watermark_id = result.stdout.strip()
            return jsonify({
                "success": True,
                "detected": True,
                "watermark_id": watermark_id,
                "confidence": 100.0
            })
        else:
            return jsonify({
                "success": True,
                "detected": False,
                "watermark_id": None,
                "confidence": 0.0
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
