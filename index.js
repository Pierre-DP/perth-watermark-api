// index.js
const express = require('express');
const speex = require('speex'); // For audio watermark embed/extract
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json({ limit: '50mb' })); // Large audio files
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// Embed watermark in audio
app.post('/api/embed', async (req, res) => {
  try {
    const { audio, watermark = 'AUDIO_WM_2025' } = req.body;

    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64) in request body' });

    // Decode base64 to buffer (assume WAV for simplicity; extend for MP3)
    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    // Write temp file
    const tempIn = path.join(__dirname, 'temp_in.wav');
    const tempOut = path.join(__dirname, 'temp_out.wav');
    fs.writeFileSync(tempIn, audioBuffer);

    // Embed using Speex (simple echo hiding for demo; production: use spread-spectrum)
    const enhancer = new speex.Enhancer();
    enhancer.setInputFile(tempIn);
    enhancer.setOutputFile(tempOut);
    enhancer.setWatermark(watermark); // Custom method (adapt lib)
    await enhancer.process(); // Async embed

    // Read output
    const watermarkedBuffer = fs.readFileSync(tempOut);
    const watermarkedBase64 = `data:audio/wav;base64,${watermarkedBuffer.toString('base64')}`;

    // Cleanup
    fs.unlinkSync(tempIn);
    fs.unlinkSync(tempOut);

    res.json({ success: true, watermarkedAudio: watermarkedBase64, embedded: watermark });
  } catch (err) {
    console.error('Embed error:', err);
    res.status(500).json({ error: 'Embed failed', details: err.message });
  }
});

// Extract watermark from audio
app.post('/api/extract', async (req, res) => {
  try {
    const { audio } = req.body;

    if (!audio) return res.status(400).json({ error: 'Missing "audio" (base64) in request body' });

    const base64Data = audio.replace(/^data:audio\/wav;base64,/, '');
    const audioBuffer = Buffer.from(base64Data, 'base64');

    const tempFile = path.join(__dirname, 'temp_extract.wav');
    fs.writeFileSync(tempFile, audioBuffer);

    const extractor = new speex.Extractor();
    extractor.setInputFile(tempFile);
    const extracted = await extractor.extractWatermark();

    fs.unlinkSync(tempFile);

    res.json({ success: true, extractedWatermark: extracted || 'No watermark found' });
  } catch (err) {
    console.error('Extract error:', err);
    res.status(500).json({ error: 'Extract failed', details: err.message });
  }
});

// Fallback / Demo page
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Audio Watermark API listening on port ${PORT}`);
});

module.exports = app;
