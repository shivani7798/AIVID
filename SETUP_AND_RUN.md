# AIVID: AI Video Explainer Generator

A production-ready system for automatically generating professional 60+ second video explainers from research PDFs using LLM deep analysis, professional voice synthesis, and intelligent annotation.

---

## System Architecture

```
input/
  └── your_paper.pdf          ← Place PDFs here
  
output/
  └── {sanitized_title}/      ← Output folder (automatic)
      ├── paper.pdf           ← Copy of original PDF
      ├── audio.mp3           ← Generated narration
      ├── timeline.json       ← Scene timing & metadata
      └── video.mp4           ← Final explainer video
```

---

## Prerequisites

- **Python 3.9+**
- **System RAM**: Minimum 4GB recommended (8GB+ for LLM inference)
- **Ollama** (optional, for advanced LLM features)
  - Install from https://ollama.ai
  - Models: `llama3.2` (3.2B, 2GB) or `llama3` (8B, 4.7GB)

---

## First-Time Setup

### 1. Clone/Download the Project
```bash
cd /path/to/AIVID
```

### 2. Install Python Dependencies
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install System Dependencies (Linux)
```bash
# For video rendering and PDF processing
brew install ffmpeg
#$sudo apt-get update
#sudo apt-get install -y libgl1-mesa-glx libsm6 libxrender1 libxext6

# For ffmpeg (video codec support)
#sudo apt-get install -y ffmpeg
```


### 4. Setup Ollama (Optional, for Best LLM Results)
```bash
# Install Ollama from https://ollama.ai

# Start Ollama service
ollama serve
# (Keep this running in a separate terminal)

# Then pull a model:
ollama pull llama3.2    # Smaller model (~2GB, recommended)
ollama pull llama3      # Larger model (~4.7GB, better quality)

```

---

## Project Structure

```
AIVID/
├── run.py              ← Main orchestrator script
├── make_video.py       ← Async video generation pipeline
├── requirements.txt    ← Python dependencies
├── input/              ← Place PDFs here
├── output/             ← Generated videos (auto-created)
└── SETUP_AND_RUN.md    ← This file
```

---

## How to Use

### Quick Start
```bash
# Activate virtual environment
source venv/bin/activate

# 1. Place your PDF in the input/ folder
cp your_paper.pdf input/

# 2. Run the pipeline
python run.py --log-level INFO

# 3. Check output folder for video
ls output/
```

### Run Options

**Standard run (uses LLM if available, fallback otherwise):**
```bash
python run.py --log-level INFO
```

**Debug mode (verbose output):**
```bash
python run.py --log-level DEBUG
```

**Warning level (errors only):**
```bash
python run.py --log-level WARNING
```

---

## Output

After running, you'll find:

**`output/{paper_title}/`**
- `video.mp4`: Final explainer video (60+ seconds)
- `audio.mp3`: Generated narration with professional voice
- `timeline.json`: Scene timing, highlights, and annotations
- `paper.pdf`: Copy of the input PDF

---

## Features

✅ **Automatic PDF Processing** — Extracts content and titles  
✅ **LLM-Powered Scripts** — Deep technical analysis (when Ollama is available)  
✅ **Professional Voice** — Edge TTS with natural speech synthesis  
✅ **On-Screen Highlights** — Auto-annotates important phrases from the paper  
✅ **Smart Fallback** — Works without LLM using fallback segments  
✅ **Comprehensive Logging** — Debug-level output for troubleshooting  

---

## Troubleshooting

### Issue: "Ollama runner process has terminated"
**Cause:** Memory constraints or Ollama service not running  
**Solution:**
```bash
# Check if Ollama is running:
ps aux | grep ollama

# If not running, start it in a separate terminal:
ollama serve

# Free up memory:
killall python  # Close other Python processes
```

### Issue: "model requires more system memory"
**Cause:** Your machine doesn't have enough RAM for the larger model  
**Solution:**
```bash
# Use smaller model:
ollama pull llama3.2

# Or check available memory:
free -h

# If low, close other applications and try again
```

### Issue: Audio is too short compared to video length
**Cause:** TTS generation took too long or was interrupted  
**Solution:**
- Check internet connection (Edge TTS requires it)
- Increase timeout in `make_video.py` if needed
- Use fallback mode if TTS hangs

### Issue: Highlights not showing on video
**Cause:** Phrase doesn't exist exactly in the PDF text  
**Solution:**
- The script tries partial matches automatically
- If still missing, fallback highlights are used
- This doesn't affect video quality

---

## Configuration

### Environment Variables
```bash
# Optional: Set logging level globally
export AIVID_LOG_LEVEL=DEBUG

# Optional: Set Ollama host (default: localhost:11434)
export OLLAMA_HOST=http://localhost:11434
```

### Modify Defaults
Edit `make_video.py`:
- `OLLAMA_MODEL = "llama3.2"` — Change to `llama3` for better quality (needs more RAM)
- `total_duration = 90` — Change video length (seconds)
- Voice: `en-US-AriaNeural` — Change to different Edge TTS voice

---

## Performance

| Task | Time |
|------|------|
| PDF text extraction | ~0.5s |
| LLM script generation | 10-30s (depends on model) |
| TTS audio generation | 3-10s |
| Video rendering | 30-60s |
| **Total** | ~1-2 minutes |

*Times vary based on PDF size and system performance.*

---

## Updates & Maintenance

### When Dependencies Change
```bash
# Refresh Python packages
pip install -r requirements.txt --upgrade

# Check for updates
ollama pull llama3.2  # Pulls latest version if available
```

### Check Dependency Versions
```bash
pip list | grep -E "pymupdf|moviepy|edge-tts|ollama"
```

### Upgrade All Packages
```bash
pip install -r requirements.txt --upgrade
```

---

## Development Notes

- **LLM Prompt**: Editable in `make_video.py` `generate_audio_and_timeline()` function
- **Video Codec**: Uses libx264 (H.264). Change in `make_video.py` if needed
- **PDF Extraction**: Reads first 12 pages. Modify in `extract_pdf_text()`
- **Audio Voice**: Change in `edge_tts.Communicate()` voice parameter

---

## Next Steps

1. **Process your first PDF:**
   ```bash
   python run.py --log-level DEBUG
   ```

2. **Customize the LLM prompt** — Edit `make_video.py` for your use case

3. **Adjust video settings** — Change duration, voice, codec as needed

4. **Monitor logs** — Use `--log-level DEBUG` to troubleshoot issues

---

## Support

- Check logs with `--log-level DEBUG` for detailed error messages
- Ensure Ollama is running: `ollama serve`
- Monitor system memory: `free -h`
- Verify PDF content is readable: `pdfinfo your_paper.pdf`

Happy video generating! 🎬
