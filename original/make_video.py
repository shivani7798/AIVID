import fitz  # PyMuPDF
import cv2
import numpy as np
import json
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from pathlib import Path
import argparse
from gtts import gTTS

def generate_audio_and_timeline(pdf_path, audio_path, timeline_path):
    """Generate audio.mp3 and timeline.json from PDF."""
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    
    # Split text into chunks (simple: by sentences or fixed length)
    sentences = text.split('. ')
    num_scenes = min(10, len(sentences), num_pages)  # Up to 10 scenes or num_pages
    chunk_size = len(sentences) // num_scenes
    scenes = []
    total_duration = 130  # seconds, like original
    duration_per_scene = total_duration / num_scenes
    
    for i in range(num_scenes):
        start = i * chunk_size
        end = (i + 1) * chunk_size if i < num_scenes - 1 else len(sentences)
        chunk_text = '. '.join(sentences[start:end])
        popup_text = chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text  # Short summary
        
        scene = {
            "start_time": i * duration_per_scene,
            "end_time": (i + 1) * duration_per_scene,
            "page_number": i,  # Scene i on page i, but capped
            "popup_text": popup_text
        }
        scenes.append(scene)
    
    # Save timeline
    with open(timeline_path, 'w') as f:
        json.dump(scenes, f, indent=2)
    
    # Generate audio
    tts = gTTS(text)
    tts.save(audio_path)
    print(f"Generated {audio_path} and {timeline_path}")
import argparse
from gtts import gTTS

def get_pdf_page_image(pdf_path, page_num, zoom=2.0):
    """Converts a PDF page to an image array."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    # Convert PyMuPDF pixmap to OpenCV Image (numpy array)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    if pix.n == 4: # If RGBA, convert to RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    doc.close()
    return img

def highlight_text_on_image(pdf_path, page_num, target_text, img, zoom=2.0):
    """Finds target_text on the PDF page and draws a red box on the image."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    
    # Search for the text to get coordinates
    text_instances = page.search_for(target_text)
    
    if text_instances:
        # Take the first instance found
        rect = text_instances[0]
        # Scale coordinates based on our zoom factor
        x0, y0, x1, y1 = [int(coord * zoom) for coord in [rect.x0, rect.y0, rect.x1, rect.y1]]
        
        # Draw a red rectangle (BGR format in OpenCV, so (0,0,255) is red)
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), 3)
    else:
        print(f"Warning: Text '{target_text}' not found on page {page_num}")
        
    doc.close()
    return img

def add_popup_box(img, text, x=50, y=50):
    """Draws a simple dark box with white text for insights."""
    # Draw dark gray background box
    cv2.rectangle(img, (x, y), (x + 600, y + 100), (40, 40, 40), -1)
    # Add white text (with better text wrapping)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    color = (255, 255, 255)
    
    # Simple text wrapping
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        if len(' '.join(current_line)) > 50:
            lines.append(' '.join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    
    y_offset = y + 30
    for line in lines[:2]:  # Max 2 lines
        cv2.putText(img, line, (x + 20, y_offset), font, font_scale, color, thickness)
        y_offset += 30
    
    return img

def create_video_segment(pdf_path, scene_data):
    """Creates a single video clip for a scene."""
    img = get_pdf_page_image(pdf_path, scene_data["page_number"])
    
    if scene_data.get("highlight_text"):
        img = highlight_text_on_image(pdf_path, scene_data["page_number"], scene_data["highlight_text"], img)
        
    if scene_data.get("popup_text"):
        img = add_popup_box(img, scene_data["popup_text"])
        
    # Convert OpenCV image (BGR) back to RGB for MoviePy
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Create a MoviePy clip that lasts for the specified duration
    duration = scene_data["end_time"] - scene_data["start_time"]
    clip = ImageClip(img_rgb).set_duration(duration)
    return clip

def main(pdf_path, audio_path, timeline_path, output_path, generate=False):
    if generate:
        generate_audio_and_timeline(pdf_path, audio_path, timeline_path)
    
    # Verify files exist
    if not Path(pdf_path).exists():
        print(f"ERROR: {pdf_path} not found.")
        return
    
    if not Path(audio_path).exists():
        print(f"ERROR: {audio_path} not found.")
        return
    
    if not Path(timeline_path).exists():
        print(f"ERROR: {timeline_path} not found.")
        return
    
    # Load Timeline
    with open(timeline_path, 'r') as f:
        timeline = json.load(f)
    
    print(f"📹 Generating video with {len(timeline)} scenes...")
    clips = []
    for i, scene in enumerate(timeline, 1):
        print(f"  [{i}/{len(timeline)}] Processing: {scene['popup_text']} (Page {scene['page_number']}, {scene['start_time']}-{scene['end_time']}s)")
        try:
            clip = create_video_segment(pdf_path, scene)
            clips.append(clip)
        except Exception as e:
            print(f"  ⚠️  Warning: Error processing scene {i}: {e}")
    
    if not clips:
        print("ERROR: No valid clips created. Check your PDF and timeline.")
        return
    
    # Stitch clips together
    print("\n🔗 Concatenating video clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Add Audio
    print("🔊 Adding audio...")
    audio = AudioFileClip(audio_path)
    final_video = final_video.set_audio(audio)
    
    # Render
    print(f"✨ Rendering final video as {output_path}...")
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", verbose=False)
    
    print(f"\n✅ Done! Your video is ready: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate video from PDF, audio, and timeline.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("--audio", default="audio.mp3", help="Path to the audio file")
    parser.add_argument("--timeline", default="timeline.json", help="Path to the timeline JSON file")
    parser.add_argument("--output", default="Final_Explainer.mp4", help="Output video file")
    parser.add_argument("--generate", action="store_true", help="Generate audio and timeline from PDF")
    
    args = parser.parse_args()
    main(args.pdf, args.audio, args.timeline, args.output, args.generate)
