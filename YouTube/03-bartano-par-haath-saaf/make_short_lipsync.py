"""Assemble the lip-synced Short (1080x1920, 25 fps).

Opens on Sameer doing the dishes, cuts to his friend asking the question, then
back to Sameer for the reply and the punchline, each with its Hindi caption
while it is spoken; the laugh track plays over the friend's face at the end.

Run (from this folder):
    uv run --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_short_lipsync.py
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image

from make_vertical_clip import RATE, WINDOW_H, WINDOW_Y, decode_mono, label_image, reframe

HERE = Path(__file__).parent
OUTPUT = HERE / "bartanon-par-haath-saaf-lipsync-short.mp4"
FPS = 25

# Where each character's face sits across the 16:9 source frame.
SAMEER_X, FRIEND_X = 0.49, 0.50

# (talking clip, voice line, face position, caption, pause after the line)
BEATS = [
    ("line1-blue-shirt", "line1", FRIEND_X, "line1", 0.35),
    ("line2-sameer", "line2", SAMEER_X, "line2", 0.50),   # the beat before the punchline
    ("line3-sameer", "line3", SAMEER_X, "line3", 0.15),   # punchline, then the laughter
]
OPENING = ("line2-sameer", SAMEER_X, 1.2)   # establishing shot: Sameer at the sink, silent
REACTION = ("line1-blue-shirt", FRIEND_X, "laughter", 0.5)   # listener's face under the laugh track
CAPTION_Y = WINDOW_Y + WINDOW_H - 300


def clip_frames(name):
    with av.open(str(HERE / "lipsync" / f"{name}-raw.mp4")) as container:
        return [frame.to_image() for frame in container.decode(video=0)]


def push_in(still, centre_x, count, amount, label):
    """`count` vertical frames of a still with a slow zoom towards the face."""
    w, h = still.size
    cache, shots = {}, []
    for k in range(count):
        zoom = 1 + amount * k / count
        cw, ch = w / zoom, h / zoom
        left, top = (w - cw) * centre_x, (h - ch) * 0.35
        zoomed = still.resize((w, h), Image.BILINEAR, box=(left, top, left + cw, top + ch))
        shots.append(reframe(zoomed, centre_x, cache, label))
    return shots


def main():
    label = label_image()
    captions = {n: Image.open(HERE / "captions" / f"{n}.png").convert("RGBA") for *_, n, _ in BEATS}
    clips = {name: clip_frames(name) for name in {b[0] for b in BEATS}}
    frames, sounds = [], []          # frames: finished vertical images; sounds: (start_s, samples)

    def add(image, caption=None):
        if caption is not None:
            image = image.copy()
            image.paste(caption, (0, CAPTION_Y), caption)
        frames.append(image)

    clip, centre_x, seconds = OPENING
    frames += push_in(clips[clip][0], centre_x, round(seconds * FPS), 0.05, label)

    for clip, voice, centre_x, caption, pause in BEATS:
        cache = {}
        shots = [reframe(f, centre_x, cache, label) for f in clips[clip]]
        samples = decode_mono(HERE / "audio" / f"{voice}.mp3")
        sounds.append((len(frames) / FPS, samples))
        spoken = round(len(samples) / RATE * FPS)
        for k, shot in enumerate(shots):
            add(shot, captions[caption] if k < spoken else None)
        for _ in range(round(pause * FPS)):       # hold the last frame for the pause
            add(shots[-1])

    # Reaction: the listener's face with a slow push-in while the laugh track plays.
    clip, centre_x, sound, tail = REACTION
    samples = decode_mono(HERE / "audio" / f"{sound}.mp3")
    sounds.append((len(frames) / FPS, samples))
    count = round((len(samples) / RATE + tail) * FPS)
    for k, image in enumerate(push_in(clips[clip][0], centre_x, count, 0.10, label)):
        if k >= count - 8:                         # fade to black at the very end
            image = Image.blend(image, Image.new("RGB", image.size), (k - (count - 8)) / 8)
        frames.append(image)

    total = len(frames) / FPS
    track = np.zeros(int((total + 0.5) * RATE))
    for start, samples in sounds:
        at = int(start * RATE)
        track[at:at + len(samples)] += samples[: len(track) - at] / 32768
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)

    with av.open(str(OUTPUT), "w") as out:
        video = out.add_stream("libx264", rate=FPS)
        video.width, video.height, video.pix_fmt = frames[0].width, frames[0].height, "yuv420p"
        video.options = {"crf": "18", "preset": "medium"}
        audio = out.add_stream("aac", rate=RATE, layout="mono")
        to_aac = av.AudioResampler(format="fltp", layout="mono", rate=RATE)
        for image in frames:
            out.mux(video.encode(av.VideoFrame.from_image(image)))
        out.mux(video.encode(None))
        for i in range(0, int(total * RATE), 1024):
            chunk = av.AudioFrame.from_ndarray(pcm[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
            chunk.sample_rate, chunk.pts = RATE, i
            for resampled in to_aac.resample(chunk):
                out.mux(audio.encode(resampled))
        out.mux(audio.encode(None))

    names = [b[1] for b in BEATS] + [REACTION[2]]
    for name, (start, samples) in zip(names, sounds):
        print(f"{name:9s} starts {start:5.2f}s, lasts {len(samples) / RATE:.2f}s")
    print(f"wrote {OUTPUT.name}: {total:.1f}s, {len(frames)} frames")


if __name__ == "__main__":
    sys.exit(main())
