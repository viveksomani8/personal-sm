"""Assemble the lip-synced Short (1080x1920, 25 fps).

Opens on the kids splashing in the river, cuts to Sameer on the bank for the
scolding and the punchline (each with its Hindi caption while it is spoken),
then back to the kids, frozen and baffled, with the laugh track over them.

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
OUTPUT = HERE / "nahane-se-haath-dho-baithoge-lipsync-short.mp4"
FPS = 25

LINE1_X, LINE2_X = 0.38, 0.46   # crop centres across the 16:9 frame (line 1 keeps the raised finger in shot)
KIDS_X = 0.50        # the kids' shots are already 4:5, so the whole frame is shown

# Opening: the kids playing, with river ambience picked out of the sound effect. An animated
# clip is used if one has been saved to clips/; otherwise the still gets a slow push-in.
OPENING_CLIP, OPENING_STILL, OPENING_SECONDS = (
    HERE / "clips" / "kids-playing-raw.mp4", HERE / "characters" / "kids-playing.png", 3.0)
AMBIENCE, AMBIENCE_FROM, AMBIENCE_PEAK, AMBIENCE_FADE = "river-kids", 2.0, 0.55, 0.25

# (talking clip, voice line, face position, caption, pause after the line)
BEATS = [
    ("line1-sameer", "line1", LINE1_X, "line1", 0.30),
    ("line2-sameer", "line2", LINE2_X, "line2", 0.10),   # punchline, then the stunned kids
]
# Reaction: still of the stunned kids, a silent beat, then the laugh track.
REACTION_STILL, REACTION_BEAT, REACTION_SOUND, REACTION_TAIL = (
    HERE / "characters" / "kids-surprised.png", 0.7, "laughter", 0.5)
CAPTION_Y = WINDOW_Y + WINDOW_H - 300


def clip_frames(path):
    """All frames of a clip, plus its frame rate."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        return [frame.to_image() for frame in container.decode(stream)], float(stream.average_rate)


def push_in(still, centre_x, count, amount, label):
    """`count` vertical frames of a still with a slow zoom towards the faces."""
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
    frames, sounds = [], []          # frames: finished vertical images; sounds: (name, start_s, samples)

    def add(image, caption=None):
        if caption is not None:
            image = image.copy()
            image.paste(caption, (0, CAPTION_Y), caption)
        frames.append(image)

    # Opening: the playing clip resampled to 25 fps (or the still), with the river ambience under it.
    count = round(OPENING_SECONDS * FPS)
    if OPENING_CLIP.exists():
        source, source_fps = clip_frames(OPENING_CLIP)
        count = min(count, int(len(source) / source_fps * FPS))
        cache = {}
        for k in range(count):
            add(reframe(source[min(int(k / FPS * source_fps), len(source) - 1)], KIDS_X, cache, label))
    else:
        still = Image.open(OPENING_STILL).convert("RGB")
        frames += push_in(still, KIDS_X, count, 0.10, label)
    ambience = decode_mono(HERE / "audio" / f"{AMBIENCE}.mp3").astype(float)
    ambience = ambience[int(AMBIENCE_FROM * RATE):][: int(count / FPS * RATE)]
    ambience *= AMBIENCE_PEAK * 32767 / np.abs(ambience).max()
    fade = int(AMBIENCE_FADE * RATE)
    ambience[:fade // 2] *= np.linspace(0, 1, fade // 2)
    ambience[-fade:] *= np.linspace(1, 0, fade)
    sounds.append((AMBIENCE, 0.0, ambience))

    for clip, voice, centre_x, caption, pause in BEATS:
        cache = {}
        source, _ = clip_frames(HERE / "lipsync" / f"{clip}-raw.mp4")
        shots = [reframe(f, centre_x, cache, label) for f in source]
        samples = decode_mono(HERE / "audio" / f"{voice}.mp3")
        sounds.append((voice, len(frames) / FPS, samples))
        spoken = round(len(samples) / RATE * FPS)
        for k, shot in enumerate(shots):
            add(shot, captions[caption] if k < spoken else None)
        for _ in range(round(pause * FPS)):       # hold the last frame for the pause
            add(shots[-1])

    # Reaction: the stunned kids with a slow push-in; a silent beat, then the laughter.
    samples = decode_mono(HERE / "audio" / f"{REACTION_SOUND}.mp3")
    sounds.append((REACTION_SOUND, len(frames) / FPS + REACTION_BEAT, samples))
    count = round((REACTION_BEAT + len(samples) / RATE + REACTION_TAIL) * FPS)
    still = Image.open(REACTION_STILL).convert("RGB")
    for k, image in enumerate(push_in(still, KIDS_X, count, 0.12, label)):
        if k >= count - 8:                         # fade to black at the very end
            image = Image.blend(image, Image.new("RGB", image.size), (k - (count - 8)) / 8)
        frames.append(image)

    total = len(frames) / FPS
    track = np.zeros(int((total + 0.5) * RATE))
    for _, start, samples in sounds:
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

    for name, start, samples in sounds:
        print(f"{name:10s} starts {start:5.2f}s, lasts {len(samples) / RATE:.2f}s")
    print(f"wrote {OUTPUT.name}: {total:.1f}s, {len(frames)} frames")


if __name__ == "__main__":
    sys.exit(main())
