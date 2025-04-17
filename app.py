
import os
import tempfile
import ssl
import subprocess
import glob
import json

import certifi
import numpy as np
import librosa
import streamlit as st
import streamlit.components.v1 as components
from yt_dlp import YoutubeDL

# 1) Streamlit page config
st.set_page_config(page_title='Live music chords', layout='wide')

# 2) SSL fix
ssl._create_default_https_context = lambda *args, **kwargs: \
    ssl.create_default_context(cafile=certifi.where(), *args, **kwargs)

# 3) Audio & chord params
SR = 44100
HOP_LENGTH = 512
N_FFT = 4096
NOTE_NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

st.title('🎸 Live Music chords generator')
st.markdown(
    "Enter a YouTube URL below, and this app will give you chords live as the video plays."
)

url = st.text_input('YouTube URL')
if not url:
    st.warning('Please paste a YouTube URL above to begin.')
else:
    vid_id = url.split('v=')[-1].split('&')[0]

    # — Download & convert audio —
    tmpf = tempfile.NamedTemporaryFile(delete=False)
    prefix = tmpf.name; tmpf.close()
    with st.spinner('Downloading and converting audio…'):
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': prefix + '.%(ext)s',
            'quiet': True
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = glob.glob(prefix + '.*')
        if not files:
            st.error('Failed to download audio; check the URL and try again.')
            st.stop()
        src = files[0]
        wav_path = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        subprocess.run(
            ['ffmpeg','-y','-i',src,'-ar',str(SR),'-ac','1',wav_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        for f in files:
            try: os.remove(f)
            except: pass

    # — Load audio —
    with st.spinner('Loading audio into memory…'):
        y, sr = librosa.load(wav_path, sr=SR, mono=True)
    try: os.remove(wav_path)
    except: pass

    # — Beat tracking & chroma extraction —
    with st.spinner('Extracting chord labels…'):
        tempo, beats = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=HOP_LENGTH
        )
        if beats.size == 0:
            beats = np.array([0])
        beat_times = librosa.frames_to_time(
            beats, sr=sr, hop_length=HOP_LENGTH
        )
        chroma = librosa.feature.chroma_stft(
            y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH
        )

        # Label each beat with the best triad template
        tmp_labels = []
        for i, b in enumerate(beats):
            start = int(b)
            end = int(beats[i+1]) if (i+1)<len(beats) else chroma.shape[1]
            seg = chroma[:, start:end] if end>start else chroma[:, start:start+1]
            avg = np.mean(seg, axis=1)
            best_lab, best_corr = '—', -1.0
            for r in range(12):
                for kind, ivs in [('maj',[0,4,7]), ('min',[0,3,7])]:
                    tpl = np.zeros(12)
                    for iv in ivs: tpl[(r+iv)%12] = 1
                    corr = np.dot(avg, tpl) / (
                        np.linalg.norm(avg)*np.linalg.norm(tpl) + 1e-6
                    )
                    if corr > best_corr:
                        best_corr, best_lab = corr, f"{NOTE_NAMES[r]}{kind}"
            tmp_labels.append(best_lab)

    # — Stabilize: keep only runs ≥2 beats —
    runs = []
    cur_lab, cur_time, count = tmp_labels[0], beat_times[0], 1
    for j in range(1, len(tmp_labels)):
        if tmp_labels[j] == cur_lab:
            count += 1
        else:
            runs.append((cur_time, cur_lab, count))
            cur_lab, cur_time, count = tmp_labels[j], beat_times[j], 1
    runs.append((cur_time, cur_lab, count))

    progression = [
        {'time': float(t), 'label': lab}
        for t, lab, cnt in runs if cnt >= 2
    ]
    if not progression:
        progression = [{'time': 0.0, 'label': tmp_labels[0]}]

    # — Embed video + live chord sync —
    prog_json = json.dumps(progression)
    placeholder = st.empty()
    html = f"""
<div style="display:flex;align-items:flex-start;">
  <iframe
    id="player-{vid_id}"
    width="640" height="360"
    src="https://www.youtube.com/embed/{vid_id}?enablejsapi=1"
    frameborder="0" allow="autoplay; encrypted-media" allowfullscreen
  ></iframe>
  <div style="margin-left:30px; text-align:center;">
    <div style="font-size:20px; color:gray;">PREVIOUS</div>
    <div id="prev-{vid_id}" style="color:gray;font-size:24px;">—</div>
    <div style="margin-top:20px; font-size:20px; color:gray;">NOW PLAYING</div>
    <div id="curr-{vid_id}" style="color:red;font-size:36px;font-weight:bold;">—</div>
    <div style="margin-top:20px; font-size:20px; color:gray;">NEXT</div>
    <div id="next-{vid_id}" style="color:gray;font-size:24px;">—</div>
  </div>
</div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
  const prog = {prog_json};
  let player;
  function initPlayer() {{
    player = new YT.Player("player-{vid_id}");
  }}
  if (window.YT && window.YT.Player) initPlayer();
  else window.onYouTubeIframeAPIReady = initPlayer;
  function updateChords() {{
    if (!player || typeof player.getCurrentTime !== "function") return;
    const t = player.getCurrentTime();
    let idx = 0;
    for (let i = 0; i < prog.length; i++) {{
      if (i+1 === prog.length || t < prog[i+1].time) {{ idx = i; break; }}
    }}
    document.getElementById("prev-{vid_id}").innerText =
      idx > 0 ? prog[idx-1].label : "—";
    document.getElementById("curr-{vid_id}").innerText = prog[idx].label;
    document.getElementById("next-{vid_id}").innerText =
      idx < prog.length-1 ? prog[idx+1].label : "—";
  }}
  setInterval(updateChords, 500);
</script>
"""
    with placeholder:
        components.html(html, height=400, scrolling=False)

    # — Full progression in an expander —
    exp = st.expander("View Full Chord Progression")
    for p in progression:
        exp.markdown(f"- **{p['label']}** @ {p['time']:.2f}s")

