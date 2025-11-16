// index.js - PURE JS AUDIO WATERMARK (NO SPEEX!)
const express = require('express');
const { WaveFile } = require('wavefile');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Health
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// EMBED
app.post('/api/embed', (req, res) => {
  try {
    const { audio, watermark = 'ZA-2025' } = req.body;
    if (!audio) return res.status(400).json({ error: 'Missing audio' });

    const base64 = audio.replace(/^data:audio\/wav;base64,/, '');
    const buffer = Buffer.from(base64, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(buffer);

    if (wav.fmt.bitsPerSample !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    const text = watermark.slice(0, 100);
    const binary = text.split('').map(c => c.charCodeAt(0).toString(2).padStart(8, '0')).join('');
    let bit = 0;

    const samples = wav.getSamples(true);
    for (let i = 0; i < samples.length && bit < binary.length; i++) {
      samples[i] = (samples[i] & ~1) | parseInt(binary[bit], 2);
      bit++;
    }

    wav.setSamples(samples);
    const out = wav.toBuffer();
    const out64 = `data:audio/wav;base64,${out.toString('base64')}`;

    res.json({ success: true, watermarkedAudio: out64, embedded: text });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// EXTRACT
app.post('/api/extract', (req, res) => {
  try {
    const { audio } = req.body;
    if (!audio) return res.status(400).json({ error: 'Missing audio' });

    const base64 = audio.replace(/^data:audio\/wav;base64,/, '');
    const buffer = Buffer.from(base64, 'base64');

    const wav = new WaveFile();
    wav.fromBuffer(buffer);

    if (wav.fmt.bitsPerSample !== 16) {
      return res.status(400).json({ error: 'Only 16-bit WAV supported' });
    }

    const samples = wav.getSamples(true);
    let bits = '';
    for (let i = 0; i < 800 && i < samples.length; i++) {
      bits += (samples[i] & 1).toString();
    }

    const bytes = bits.match(/.{8}/g) || [];
    let text = '';
    for (const b of bytes) {
      const char = String.fromCharCode(parseInt(b, 2));
      if (char === '\0') break;
      text += char;
    }

    res.json({ success: true, extractedWatermark: text || 'None' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Demo UI
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Audio Watermark API LIVE on port ${PORT}`);
});
