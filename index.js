// index.js - Pure JS Audio Watermark (wavefile v11.0.0)
const express = require('express');
const WaveFile = require('wavefile').WaveFile; // Correct import for v11
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// EMBED WATERMARK
app.post('/api/embed', (req, res) => {
  try {
    const { audio, watermark = 'ZA-2025' } = req.body;
    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64 WAV)' });

    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(audioBuffer);

    if (wav.fmt.bitsPerSample !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    // Watermark to binary (up to 100 chars)
    const wmText = watermark.slice(0, 100);
    const wmBinary = wmText.split('').map(c => c.charCodeAt(0).toString(2).padStart(8, '0')).join('');
    let bitIndex = 0;

    // Get interleaved samples
    const samples = wav.toSampleRate(wav.fmt.sampleRate).getSamples(true);
    for (let i = 0; i < samples.length && bitIndex < wmBinary.length; i++) {
      samples[i] = (samples[i] & ~1) | parseInt(wmBinary[bitIndex], 2);
      bitIndex = (bitIndex + 1) % wmBinary.length; // Cycle if needed
    }

    // Set samples back
    wav.fromScratch(wav.fmt.numChannels, wav.fmt.sampleRate, '16', samples);
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

// EXTRACT WATERMARK
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

    // Get interleaved samples
    const samples = wav.toSampleRate(wav.fmt.sampleRate).getSamples(true);
    let extractedBits = '';
    for (let i = 0; i < samples.length && extractedBits.length < 800; i++) { // 800 bits ~100 chars
      extractedBits += (samples[i] & 1).toString();
    }

    // Binary to text
    const bytes = extractedBits.match(/.{8}/g) || [];
    let extractedText = '';
    for (const byte of bytes) {
      const charCode = parseInt(byte, 2);
      if (charCode === 0) break; // Null terminator
      extractedText += String.fromCharCode(charCode);
    }

    res.json({
      success: true,
      extractedWatermark: extractedText || 'No watermark found'
    });
  } catch (err) {
    console.error('Extract error:', err);
    res.status(500).json({ error: 'Extract failed', details: err.message });
  }
});

// Serve demo UI
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Audio Watermark API running on port ${PORT}`);
});

module.exports = app;
