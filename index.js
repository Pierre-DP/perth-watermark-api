// index.js
const express = require('express');
const WaveFile = require('wavefile').WaveFile;
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json({ limit: '50mb' })); // Big audio files
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// Embed watermark (LSB steganography in WAV samples)
app.post('/api/embed', async (req, res) => {
  try {
    const { audio, watermark = 'AUDIO_WM_2025' } = req.body;

    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64 WAV) in request body' });

    // Decode base64 (assume WAV)
    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    // Parse WAV
    const wav = new WaveFile();
    wav.fromBuffer(audioBuffer);

    if (wav.bitDepth !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    // Convert watermark to binary (8 chars max for demo; extend as needed)
    const wmBinary = watermark.slice(0, 8).split('').map(c => c.charCodeAt(0).toString(2).padStart(8, '0')).join('');
    let bitIndex = 0;

    // Embed in LSB of each sample (mono/stereo safe)
    for (let i = 0; i < wav.data.samples.length && bitIndex < wmBinary.length; i++) {
      const sample = wav.data.samples[i];
      if (Array.isArray(sample)) { // Stereo
        sample[0] = (sample[0] & 0xFFFE) | parseInt(wmBinary[bitIndex++ % wmBinary.length]); // Cycle bits if needed
        if (bitIndex < wmBinary.length) {
          sample[1] = (sample[1] & 0xFFFE) | parseInt(wmBinary[bitIndex++ % wmBinary.length]);
        }
      } else { // Mono
        wav.data.samples[i] = (sample & 0xFFFE) | parseInt(wmBinary[bitIndex++ % wmBinary.length]);
      }
    }

    // Export watermarked WAV
    wav.toSampleRate(wav.container.sampleRate);
    const watermarkedBuffer = wav.toBuffer();
    const watermarkedBase64 = `data:audio/wav;base64,${watermarkedBuffer.toString('base64')}`;

    res.json({ success: true, watermarkedAudio: watermarkedBase64, embedded: watermark });
  } catch (err) {
    console.error('Embed error:', err);
    res.status(500).json({ error: 'Embed failed', details: err.message });
  }
});

// Extract watermark
app.post('/api/extract', async (req, res) => {
  try {
    const { audio } = req.body;

    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64 WAV) in request body' });

    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(audioBuffer);

    if (wav.bitDepth !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    // Extract LSB bits (first 64 bits → 8 chars)
    let extractedBits = '';
    for (let i = 0; i < 64 && i < wav.data.samples.length; i++) { // 64 bits for 8 chars
      const sample = wav.data.samples[i];
      if (Array.isArray(sample)) {
        extractedBits += (sample[0] & 1).toString();
        if (i * 2 + 1 < 64) extractedBits += (sample[1] & 1).toString();
      } else {
        extractedBits += (sample & 1).toString();
      }
    }

    // Convert binary to text
    const extracted = extractedBits.match(/.{8}/g)?.map(bin => String.fromCharCode(parseInt(bin, 2))).join('') || 'No watermark';

    res.json({ success: true, extractedWatermark: extracted });
  } catch (err) {
    console.error('Extract error:', err);
    res.status(500).json({ error: 'Extract failed', details: err.message });
  }
});

// Fallback / Demo
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Audio Watermark API listening on port ${PORT}`);
});

module.exports = app;
