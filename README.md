# 🎸 ChordStream

A simple Streamlit app that takes a YouTube URL, extracts a stable chord progression, and shows “Previous”, “Now Playing” and “Next” chords in sync with the video.

## Features

- Paste any YouTube link—no uploads needed    
- Live chord display alongside the embedded video  
- Expandable list of the full progression

## Requirements

- Python 3.8+  
- [FFmpeg](https://ffmpeg.org/) on your PATH  

## Quickstart

1. Clone this repo and enter its directory  
2. Create a virtual environment and activate it:  
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
3. Install Python dependencies:

   ```bash
   pip install streamlit yt-dlp librosa numpy certifi

   
4. Run the app:

   ```bash
   streamlit run streamlit_chordify.py
