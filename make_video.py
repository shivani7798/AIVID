import fitz  # PyMuPDF
import cv2
import numpy as np
import json
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from pathlib import Path
import ollama
import asyncio
import edge_tts
import logging
import time

OLLAMA_MODEL = "llama3.2"

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF."""
    start_time = time.time()
    logging.info(f"[PDF] Opening {pdf_path}")
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    logging.info(f"[PDF] Pages: {num_pages}. Reading all pages.")
    
    text = ""
    for i in range(num_pages):
        page_start = time.time()
        page = doc.load_page(i)
        page_text = page.get_text()
        # Skip pages that are likely references
        lines = page_text.split('\n')[:10]  # check first 10 lines
        if any("reference" in line.lower() or "bibliography" in line.lower() for line in lines):
            logging.info(f"[PDF] Skipping page {i} (likely references)")
            continue
        text += page_text + "\n"
        page_elapsed = time.time() - page_start
        logging.debug(f"[PDF] Page {i}: {len(page_text)} chars in {page_elapsed:.2f}s")
    
    doc.close()
    elapsed = time.time() - start_time
    logging.info(f"[PDF] Extraction complete: {len(text)} chars in {elapsed:.2f}s")
    return text


def call_ollama(prompt: str) -> str:
    """Try the available Ollama models until one produces a response."""
    for model in ["llama3.2", "llama3"]:
        try:
            logging.info(f"[OLLAMA] Sending prompt to {model}")
            response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
            return response["message"]["content"]
        except Exception as e:
            logging.warning(f"[OLLAMA] {model} failed: {e}")
    raise RuntimeError("All Ollama model requests failed.")


def deduplicate_lines(text):
    seen = set()
    result = []
    for line in text.split("\n"):
        if line.strip() and line not in seen:
            result.append(line)
            seen.add(line)
    return "\n".join(result)
    """Split text into chunks of approximately chunk_size characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # Try to break at a paragraph or sentence
            while end > start and text[end] not in '\n\n':
                end -= 1
            if end == start:
                end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def resolve_highlight_page(pdf_path: Path, highlight: str, default_page: int) -> int:
    """Find the best page containing the highlight phrase."""
    if not highlight:
        return default_page
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    highlight = highlight.strip()
    for delta in range(num_pages):
        candidate_page = (default_page + delta) % num_pages
        page = doc.load_page(candidate_page)
        if page.search_for(highlight):
            doc.close()
            return candidate_page

    # Try partial phrase matches to find the most likely page
    words = [w for w in highlight.split() if w.isalpha()]
    for length in range(min(5, len(words)), 1, -1):
        snippet = " ".join(words[:length])
        for page_index in range(num_pages):
            page = doc.load_page(page_index)
            if page.search_for(snippet):
                doc.close()
                return page_index

    doc.close()
    return default_page


async def generate_audio_and_timeline(output_folder: Path):
    """Generate audio.mp3 and timeline.json from PDF using LLM for deep analysis."""
    pdf_path = output_folder / "paper.pdf"
    audio_path = output_folder / "audio.mp3"
    timeline_path = output_folder / "timeline.json"
    
    text = extract_pdf_text(pdf_path)
    
    # Chunk the text and summarize each chunk
    chunks = split_text_into_chunks(text, chunk_size=5000)
    summaries = []
    for i, chunk in enumerate(chunks):
        summary_prompt = f"""
You are a senior AI engineer reading a research paper.

Extract:
- key mechanisms (how it works)
- architecture decisions
- trade-offs and limitations

Avoid generic summaries. Focus on technical reasoning.

Text:
{chunk}
"""
        try:
            summary = call_ollama(summary_prompt)
            summaries.append(summary)
            logging.info(f"[SUMMARY] Chunk {i+1} summarized")
        except Exception as e:
            logging.warning(f"[SUMMARY] Failed to summarize chunk {i+1}: {e}")
            summaries.append(chunk[:500])  # Fallback to truncated chunk
    
    paper_content = deduplicate_lines("\n\n".join(summaries))
    
    # LLM Prompt
    prompt = f"""
You are a Senior AI Engineering Architect creating a detailed, accessible technical explainer
video for engineers who want actionable insight. Read the paper content below and identify the
most important 5-7 technical highlights, architecture choices, tradeoffs, and deployment risks.

Paper content:
{paper_content[:60000]}

Return ONLY a JSON object — no markdown, no preamble — with this exact structure:
{{
  "title": "Short paper title",
  "segments": [
    {{
      "text": "Narration text for this segment, 10 seconds of clear and confident engineering explanation.",
      "highlight": "short phrase that appears verbatim in the paper",
      "annotation": "Full sentence explaining why this highlight matters for design, performance, or reliability.",
      "page": 0
    }}
  ]
}}

Rules:
- Create 5-7 segments.
- Each segment should be a distinct, important idea from the paper, prioritizing depth over rigid structure.
- Use accessible engineering language: no jargon-heavy sentences, but maintain technical depth.
- "highlight" must be a short phrase that appears verbatim in the paper text above.
- "annotation" should explain why the highlight matters for design, performance, or reliability.
- "page" is 0-indexed and should point to the page containing the highlight phrase.
- Each segment MUST use a DIFFERENT page number. No page may appear twice.
- Spread pages across the paper: segments from pages 0-5, 6-20, 21+.
- Narration should sound like a senior AI engineer explaining architecture, cost, and practical deployment.
- Aim for ~60 seconds total narration.
- Do not output anything outside the JSON object.
"""
    
    char_count = len(prompt)
    logging.info(f"[OLLAMA] Prompt size: {char_count} chars")
    start_time = time.time()
    
    data = None
    for attempt in range(3):
        try:
            llm_output = call_ollama(prompt)
            data = json.loads(llm_output)
            segments = data.get("segments", [])
            if 5 <= len(segments) <= 7:
                break
            else:
                logging.warning(f"Attempt {attempt+1}: Expected 5-7 segments, got {len(segments)}, retrying...")
        except Exception as e:
            logging.warning(f"Attempt {attempt+1}: LLM failed or produced invalid output ({e}), retrying...")
    
    if data is None or not (5 <= len(segments) <= 7):
        logging.warning("All attempts failed, using fallback segments")
        segments = [
            {"text": "This paper introduces a model architecture focused on efficiency and production readiness.", "highlight": "model architecture", "annotation": "Core design principle for the paper.", "page": 0},
            {"text": "The team balances compute costs with accuracy through careful model scaling and pruning.", "highlight": "compute costs", "annotation": "Shows how cost is managed in deployment.", "page": 1},
            {"text": "Memory optimization is emphasized to support longer context windows without blowing up resource usage.", "highlight": "memory optimization", "annotation": "Critical for real-world inference workloads.", "page": 2},
            {"text": "Experimental results measure latency, throughput, and tradeoffs across different system configurations.", "highlight": "experimental results", "annotation": "Important for evaluating model performance.", "page": 3},
            {"text": "The paper highlights robustness, failure modes, and the need for stable training pipelines.", "highlight": "failure modes", "annotation": "Operationally important for reliability.", "page": 4},
            {"text": "Future work outlines practical extensions for larger models and multimodal applications.", "highlight": "future work", "annotation": "Research direction for scaling the system.", "page": 5}
        ]
    
    elapsed = time.time() - start_time
    logging.info(f"[OLLAMA] Response received in {elapsed:.2f}s")
    logging.debug(f"[OLLAMA] Raw response preview: {llm_output[:400] if 'llm_output' in locals() else 'N/A'}")
    logging.info(f"[OLLAMA] Parsed {len(segments)} segments from LLM")
    
    # Generate audio with edge-tts first so the video duration can match the narration
    narration_texts = [seg.get("text", "") for seg in segments]
    full_text = "\n\n".join(narration_texts)
    char_count = len(full_text)
    logging.info(f"[TTS] Generating audio: {char_count} chars → {audio_path}")
    start_time = time.time()
    communicate = edge_tts.Communicate(full_text, voice="en-US-AriaNeural")
    await communicate.save(audio_path)
    elapsed = time.time() - start_time
    logging.info(f"[TTS] Audio saved in {elapsed:.2f}s")

    # Determine actual audio duration and assign scene durations proportionally
    audio_clip = AudioFileClip(str(audio_path))
    audio_duration = audio_clip.duration
    audio_clip.close()
    logging.info(f"[TTS] Audio duration is {audio_duration:.2f}s")
    duration_per_segment = audio_duration / len(segments)

    timeline = []
    for i, seg in enumerate(segments):
        desired_page = seg.get("page", i)
        highlight_text = seg.get("highlight", "")
        actual_page = resolve_highlight_page(pdf_path, highlight_text, desired_page)
        scene = {
            "start_time": i * duration_per_segment,
            "end_time": (i + 1) * duration_per_segment,
            "page_number": actual_page,
            "popup_text": seg.get("annotation", f"Key insight for segment {i+1}"),
            "highlight_text": highlight_text,
            "annotation_text": seg.get("annotation", ""),
            "narration_text": seg.get("text", "")
        }
        timeline.append(scene)
    
    with open(timeline_path, 'w') as f:
        json.dump(timeline, f, indent=2)

def get_pdf_page_image(pdf_path: Path, page_num: int, zoom: float = 2.0):
    """Converts a PDF page to an image array."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    # Convert PyMuPDF pixmap to OpenCV Image (numpy array)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4:  # If RGBA, convert to RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    doc.close()
    return img

def highlight_text_on_image(pdf_path: Path, page_num: int, target_text: str, img, zoom: float = 2.0):
    """Finds target_text on the PDF page and draws a red box on the image."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    
    target_text = target_text.strip()
    text_instances = page.search_for(target_text)

    if not text_instances:
        words = [w for w in target_text.split() if w.isalpha()]
        for length in range(min(5, len(words)), 1, -1):
            phrase = " ".join(words[:length])
            if phrase:
                text_instances = page.search_for(phrase)
                if text_instances:
                    logging.debug(f"[RENDER] Found variant phrase '{phrase}' for highlight")
                    break

    if not text_instances and len(target_text.split()) > 3:
        for length in range(min(5, len(target_text.split())), 1, -1):
            fallback_phrase = " ".join(target_text.split()[:length])
            text_instances = page.search_for(fallback_phrase)
            if text_instances:
                logging.debug(f"[RENDER] Found fallback phrase '{fallback_phrase}' for highlight")
                break
    
    if text_instances:
        rect = text_instances[0]
        x0, y0, x1, y1 = [int(coord * zoom) for coord in [rect.x0, rect.y0, rect.x1, rect.y1]]
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), 4)
        cv2.putText(img, "RESEARCH HIGHLIGHT", (x0, max(25, y0 - 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.line(img, (x0, y0 - 5), (x1, y0 - 5), (0, 0, 255), 2)
        logging.debug(f"[RENDER] Highlight '{target_text}' found at ({x0},{y0})–({x1},{y1})")
    else:
        logging.warning(f"[RENDER] Highlight '{target_text}' not found on page {page_num}")
    
    doc.close()
    return img


def add_popup_box(img, text: str, x: int = 50, y: int = 50):
    """Draws a simple dark box with white text for insights."""
    cv2.rectangle(img, (x, y), (x + 700, y + 140), (30, 30, 30), -1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.75
    thickness = 2
    color = (255, 255, 255)
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        if len(' '.join(current_line)) > 42:
            lines.append(' '.join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    
    y_offset = y + 30
    for line in lines[:4]:
        cv2.putText(img, line, (x + 20, y_offset), font, font_scale, color, thickness)
        y_offset += 27
    
    return img

def create_video_segment(pdf_path: Path, scene_data: dict):
    """Creates a single video clip for a scene."""
    page_num = scene_data["page_number"]
    img = get_pdf_page_image(pdf_path, page_num)
    h, w = img.shape[:2]
    logging.debug(f"[RENDER] Rasterised page {page_num}: {w}×{h}px")
    
    if scene_data.get("highlight_text"):
        img = highlight_text_on_image(pdf_path, page_num, scene_data["highlight_text"], img)
        
    if scene_data.get("popup_text"):
        img = add_popup_box(img, scene_data["popup_text"])
        
    # Convert OpenCV image (BGR) back to RGB for MoviePy
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Create a MoviePy clip that lasts for the specified duration
    duration = scene_data["end_time"] - scene_data["start_time"]
    clip = ImageClip(img_rgb).set_duration(duration)
    return clip

async def main(output_folder: Path, generate: bool = True):
    """Main function to generate video from PDF in output_folder."""
    pdf_path = output_folder / "paper.pdf"
    audio_path = output_folder / "audio.mp3"
    timeline_path = output_folder / "timeline.json"
    video_path = output_folder / "video.mp4"
    
    if generate:
        await generate_audio_and_timeline(output_folder)
    
    # Verify files exist
    if not pdf_path.exists():
        logging.error(f"ERROR: {pdf_path} not found.")
        return
    
    if not audio_path.exists():
        logging.error(f"ERROR: {audio_path} not found.")
        return
    
    if not timeline_path.exists():
        logging.error(f"ERROR: {timeline_path} not found.")
        return
    
    # Load Timeline
    with open(timeline_path, 'r') as f:
        timeline = json.load(f)
    
    logging.info(f"📹 Generating video with {len(timeline)} scenes...")
    clips = []
    for i, scene in enumerate(timeline, 1):
        popup = scene['popup_text']
        page = scene['page_number']
        highlight = scene.get('highlight_text', '')
        start = scene['start_time']
        end = scene['end_time']
        logging.info(f"[RENDER] Processing scene {i}/{len(timeline)}: page={page}, highlight='{highlight}'")
        
        try:
            clip = create_video_segment(pdf_path, scene)
            clips.append(clip)
        except Exception as e:
            logging.error(f"Warning: Error processing scene {i}: {e}")
    
    if not clips:
        logging.error("ERROR: No valid clips created. Check your PDF and timeline.")
        return
    
    # Stitch clips together
    logging.info(f"[RENDER] Concatenating {len(clips)} clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Add Audio
    logging.info("🔊 Adding audio...")
    audio = AudioFileClip(str(audio_path))
    final_video = final_video.set_audio(audio)
    
    # Render
    logging.info(f"[RENDER] Writing video: {video_path}")
    start_time = time.time()
    final_video.write_videofile(str(video_path), fps=24, codec="libx264", audio_codec="aac", verbose=False)
    elapsed = time.time() - start_time
    logging.info(f"Video rendered in {elapsed:.2f}s")
    
    logging.info(f"[DONE] Output folder: {output_folder}")
