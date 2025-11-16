// index.js
const express = require('express');
const { WaveFile } = require('wavefile');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// === EMBED WATERMARK ===
app.post('/api/embed', (req, res) => {
  try {
    const { audio, watermark = 'AUDIO_WM_2025' } = req.body;
    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64 WAV)' });

    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(audioBuffer);

    if (wav.fmt.bitsPerSample !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    // Convert watermark to binary (max 100 chars)
    const wmText = watermark.slice(0, 100);
    const wmBinary = wmText.split('').map(c => c.charCodeAt(0).toString(2).padStart(8, '0')).join('');
    let bitIndex = 0;

    // Embed in LSB of each sample
    const samples = wav.getSamples(true); // interleaved
    for (let i = 0; i < samples.length && bitIndex < wmBinary.length; i++) {
      samples[i] = (samples[i] & ~1) | parseInt(wmBinary[bitIndex], 2);
      bitIndex++;
    }

    wav.setSamples(samples);

    const watermarkedBuffer = wav.toBuffer();
    const watermarkedBase64 = `data:audio/wav;base64,${watermarkedBuffer.toString('base64')}`;

    res.json({
      success: true,
      watermarkedAudio: watermarkedBase64,
      embedded: wmText,
      bitsEmbedded: wmBinary.length
    });
  } catch (err) {
    console.error('Embed error:', err);
    res.status(500).json({ error: 'Embed failed', details: err.message });
  }
});

// === EXTRACT WATERMARK ===
app.post('/api/extract', (req, res) => {
  try {
    const { audio } = req.body;
    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64 WAV)' });

    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(audioBuffer);

    if (wav.fmt.bitsPerSample !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    const samples = wav.getSamples(true);
    let bits = '';
    for (let i = 0; i < samples.length && bits.length < 800; i++) {
      bits += (samples[i] & 1).toString();
    }

    // Extract full bytes
    const bytes = bits.match(/.{8}/g) || [];
    let extracted = '';
    for (const byte of bytes) {
      const char = String.fromCharCode(parseInt(byte, 2));
      if (char === '\0') break;
      extracted += char;
    }

    res.json({
      success: true,
      extractedWatermark: extracted || 'No watermark found'
    });
  } catch (err) {
    console.error('Extract error:', err);
    res.status(500).json({ error: 'Extract failed', details: err.message });
  }
});

// Fallback to demo UI
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Audio Watermark API running on port ${PORT}`);
});
