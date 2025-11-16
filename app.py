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
import subprocess             # <-- ADDED: For running audiowmark
import tempfile               # <-- ADDED: For concurrency safety

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
        # Assuming non-URI format implies a default mime type for base64 decode
        mime = 'audio/wav'
        audio_bytes = base64.b64decode(audio_b64)

    # Detect format and convert to WAV
    if 'audio/mpeg' in mime or 'mp3' in mime.lower():
        audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
    elif 'audio/aac' in mime or 'aac' in mime.lower():
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format='aac')
    else:
        # Default to wav if format is unknown or not explicitly handled
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
        # NOTE: Perth's default watermark is 'default', which corresponds to a 64-bit ID of all zeros.
        # This ID is NOT what audiowmark will extract unless you specifically use audiowmark's 'default' ID.
        watermarked_audio = wm.apply_watermark(audio_data, sample_rate=sr, watermark='default') 

    # Encode output
    out_buffer = io.BytesIO()
    sf.write(out_buffer, watermarked_audio, sr, format='WAV')
    wav_out = out_buffer.getvalue()
    out_buffer.seek(0)

    # Convert to desired output format
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
    tmp_in = None
    tmp_out = None
    try:
        data = request.get_json()
        if not data or 'audio' not in data or 'watermark_id' not in data:
            return jsonify({"success": False, "error": "Missing 'audio' or 'watermark_id'"}), 400

        audio_b64 = data['audio']
        watermark_id = data['watermark_id']  # e.g., "WM-1234567890-ABC123DE"
        
        # Decode audio
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        audio_bytes = base64.b64decode(audio_b64)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            tmp_in = f.name
            f.write(audio_bytes)
        
        # Create temp output file
        tmp_out = tempfile.mktemp(suffix='_watermarked.wav')
        
        # Run audiowmark add
        result = subprocess.run(
            ['audiowmark', 'add', tmp_in, tmp_out, watermark_id],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            raise Exception(f"audiowmark add failed: {result.stderr}")
        
        # Read watermarked audio
        with open(tmp_out, 'rb') as f:
            watermarked_bytes = f.read()
        
        watermarked_b64 = f"data:audio/wav;base64,{base64.b64encode(watermarked_bytes).decode()}"
        
        return jsonify({
            "success": True,
            "watermarked_audio": watermarked_b64,
            "watermark_id": watermark_id
        })
        
    except Exception as e:
        print(f"Error in /watermark: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if tmp_in and os.path.exists(tmp_in):
            os.remove(tmp_in)
        if tmp_out and os.path.exists(tmp_out):
            os.remove(tmp_out)



@app.route('/detect', methods=['POST'])
def detect():
    # Existing Perth detection logic (confidence score)
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
        detected = bool(confidence > 0.5)

        return jsonify({
            "success": True,
            "detected": detected,
            "confidence": confidence_percent,
            "watermark_id": None
        })
    except Exception as e:
        print(f"Error in /detect: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------------------------------------------------------------
# NEW ENDPOINT: AUDIOWMARK DETECTION (ID extraction)
# ----------------------------------------------------------------------

@app.route('/detect-id', methods=['POST'])
def detect_id():
    """
    Extracts watermark ID using the audiowmark command line tool.
    Uses tempfile for concurrency safety.
    """
    tmp_path = None
    try:
        data = request.get_json()
        if not data or 'audio' not in data:
             return jsonify({"success": False, "error": "Missing 'audio' key in request body"}), 400
             
        audio_b64 = data['audio']
        
        # Decode the audio data
        if audio_b64.startswith('data:'):
            audio_b64 = audio_b64.split(',', 1)[1]
        audio_bytes = base64.b64decode(audio_b64)

        # CRITICAL FIX: Use tempfile to create a unique file for concurrent requests
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)
        
        # Run audiowmark extract
        result = subprocess.run(
            ['audiowmark', 'get', tmp_path],
            capture_output=True,
            text=True,
            check=False # Do not raise exception on non-zero return code
        )

        # Process result
        if result.returncode == 0:
            watermark_id = result.stdout.strip()
            return jsonify({
                "success": True,
                "detected": True,
                "watermark_id": watermark_id,
                "confidence": 100.0
            })
        else:
            # audiowmark returns non-zero for both errors and "no detection"
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
        print(f"An unexpected error occurred in /detect-id: {e}")
        return jsonify({"success": False, "error": f"Internal Server Error: {str(e)}"}), 500
    finally:
        # Clean up the temporary file immediately
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
