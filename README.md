# AIVID - AI Video Explainer Generator

## Quick Setup for Any PDF

### 1. Place PDFs in the `input` Folder
Put one or more PDF files into the `input/` folder.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Process All PDFs
```bash
python batch_process.py
```

This will:
- Move PDFs from `input/` to `read_pdf/`
- Automatically generate audio narration and timeline from PDF content
- Create videos in `read_pdf/` folder

### File Structure
```
AIVID/
├── input/           # Place your PDFs here
├── read_pdf/        # Processed PDFs and generated videos
├── make_video.py    # Core video generation script
├── batch_process.py # Batch processing script
├── requirements.txt # Python dependencies
```

### Manual Usage
For a single PDF with custom audio/timeline:
```bash
python make_video.py path/to/your.pdf --audio path/to/audio.mp3 --timeline path/to/timeline.json --output output.mp4
```

To auto-generate audio and timeline:
```bash
python make_video.py path/to/your.pdf --generate --output output.mp4
```
├── README.md          # This file
├── paper.pdf          # Input: Your research paper
└── audio.mp3          # Input: Your voiceover audio
```

### How the Script Works

The `make_video.py` script:

1. **Reads Timeline**: Loads timestamps, page numbers, and text from `timeline.json`
2. **Extracts PDF Pages**: Converts PDF pages to high-resolution images (2x zoom)
3. **Highlights Text**: Finds and draws red boxes around key concepts
4. **Adds Annotations**: Displays explanation popups synchronized to audio
5. **Syncs Audio**: Combines video clips with your voiceover
6. **Renders MP4**: Creates final video at 24 FPS

### Timeline Schema

Each scene in `timeline.json`:
```json
{
  "start_time": 0,           # Audio timestamp (seconds)
  "end_time": 15,            # When scene ends
  "page_number": 0,          # PDF page (0-indexed)
  "highlight_text": "Key text from paper",
  "popup_text": "Explanation to display"
}
```

### Tips

- **Text Matching**: `highlight_text` must be exact match from PDF
- **Page Numbers**: First page = 0, second page = 1, etc.
- **Timestamps**: Match exactly with your audio segments
- **Custom Styling**: Edit `add_popup_box()` in `make_video.py` for colors/positioning

---

## Dependencies

- **PyMuPDF** - PDF extraction
- **MoviePy** - Video composition
- **OpenCV** - Image processing
- **NumPy** - Array operations
- **Pandas** - Data handling

---

**Your explainer video is ready to create! 🎬**
