import subprocess
import json
import base64
import tempfile
import os
from flask import Flask, request, jsonify

# Initialize the Flask application
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for Railway deployment."""
    # This will return HTTP 200 OK
    return jsonify({"status": "ok", "message": "API is running"}), 200


@app.route('/detect-id', methods=['POST'])
def detect_id():
    """
    Accepts base64 encoded audio, runs audiowmark 'get' command, 
    and returns the detected watermark ID.
    """
    tmp_path = None
    try:
        data = request.get_json()
        audio_b64 = data['audio']
        
        # 1. Handle base64 data URI format if present
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        
        audio_bytes = base64.b64decode(audio_b64)

        # 2. Use tempfile for safe concurrent file handling (CRITICAL for Gunicorn/workers)
        # delete=False is used so we can access the file by path before manual deletion
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)
        
        # 3. Run audiowmark extract
        result = subprocess.run(
            ['audiowmark', 'get', tmp_path],
            capture_output=True,
            text=True,
            check=False 
        )

        # 4. Process result
        if result.returncode == 0:
            watermark_id = result.stdout.strip()
            return jsonify({
                "success": True,
                "detected": True,
                "watermark_id": watermark_id,
                "confidence": 100.0
            })
        else:
            # Command failed or no watermark detected (non-zero exit code)
            print(f"audiowmark failed. Return Code: {result.returncode}. Stderr: {result.stderr.strip()}")
            return jsonify({
                "success": True,
                "detected": False,
                "watermark_id": None,
                "confidence": 0.0
            })
            
    except KeyError:
        return jsonify({"success": False, "error": "Missing 'audio' key in request body"}), 400
    except Exception as e:
        # Catch other errors like malformed base64 or internal server issues
        print(f"An unexpected error occurred: {e}")
        return jsonify({"success": False, "error": f"Internal Server Error: {str(e)}"}), 500
    finally:
        # 5. Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == '__main__':
    # This block is usually ignored when running with Gunicorn
    app.run(debug=True, port=5000)
