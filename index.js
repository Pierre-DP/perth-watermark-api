// index.js
const express = require('express');
const sharp = require('sharp');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json({ limit: '10mb' })); // Handle large base64 images
app.use(express.urlencoded({ extended: true }));

// Serve static files (optional)
app.use(express.static('public'));

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'OK', port: PORT, uptime: process.uptime() });
});

// Watermark API endpoint
app.post('/api/watermark', async (req, res) => {
  try {
    const { image, text = 'CONFIDENTIAL', position = 'southeast', opacity = 0.5 } = req.body;

    if (!image) {
      return res.status(400).json({ error: 'Missing image in request body' });
    }

    // Extract base64 data (remove data:image/...;base64, prefix if present)
    const base64Data = image.replace(/^data:image\/\w+;base64,/, '');
    const imageBuffer = Buffer.from(base64Data, 'base64');

    // Generate watermark SVG
    const svg = `
      <svg>
        <text 
          x="10" 
          y="30" 
          font-family="Arial, sans-serif" 
          font-size="40" 
          font-weight="bold" 
          fill="rgba(255,255,255,${opacity})" 
          stroke="rgba(0,0,0,${opacity})" 
          stroke-width="2"
          paint-order="stroke fill">
          ${text}
        </text>
      </svg>
    `;

    const svgBuffer = Buffer.from(svg);

    // Composite watermark
    const outputBuffer = await sharp(imageBuffer)
      .composite([
        {
          input: svgBuffer,
          gravity: position, // southeast, center, north, etc.
          blend: 'over'
        }
      ])
      .png()
      .toBuffer();

    const outputBase64 = `data:image/png;base64,${outputBuffer.toString('base64')}`;

    res.json({
      success: true,
      watermarkedImage: outputBase64
    });
  } catch (error) {
    console.error('Watermark error:', error);
    res.status(500).json({ error: 'Failed to process image', details: error.message });
  }
});

// Fallback route
app.get('*', (req, res) => {
  res.send(`
    <h1>Perth Watermark API</h1>
    <p>POST to <code>/api/watermark</code> with JSON:</p>
    <pre>
{
  "image": "data:image/jpeg;base64,...",
  "text": "CONFIDENTIAL",
  "position": "southeast",
  "opacity": 0.6
}
    </pre>
    <p><a href="/health">Health Check</a></p>
  `);
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Watermark API running on port ${PORT}`);
});

module.exports = app;
