// server.js (ESM version)
import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

// Required to get __dirname in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 4173;

// Serve static files from dist
app.use(express.static(path.join(__dirname, 'dist')));

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});


app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
