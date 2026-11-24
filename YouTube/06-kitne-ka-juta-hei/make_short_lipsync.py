"""Assemble the lip-synced Short (1080x1920, 25 fps).

The wife shows off her new golden sandals, the husband gasps at what "the shoe"
must have cost (each line with its Hindi caption while it is spoken), then the
shot returns to the wife, now furious, with the laugh track over her.

Run (from this folder):
    uv run --system-certs --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_short_lipsync.py
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image

from make_vertical_clip import RATE, WINDOW_H, WINDOW_Y, decode_mono, label_image, reframe

HERE = Path(__file__).parent
OUTPUT = HERE / "kitne-ka-juta-hai-lipsync-short.mp4"
FPS = 25

WIFE_X, HUSBAND_X = 0.48, 0.49   # crop centres across the 16:9 frame (the wife's keeps both sandals in shot)

# (talking clip, voice line, face position, caption, pause after the line)
BEATS = [
    ("line1-wife", "line1", WIFE_X, "line1", 0.30),
    ("line2-husband", "line2", HUSBAND_X, "line2", 0.15),
]
# Reaction: still of the furious wife, a silent beat, then the laugh track.
REACTION_STILL, REACTION_X, REACTION_BEAT, REACTION_SOUND, REACTION_TAIL = (
    HERE / "characters" / "wife-angry.png", 0.40, 0.6, "laughter", 0.5)
CAPTION_Y = WINDOW_Y + WINDOW_H - 300
# Silent lead-in before the first line: the first frame of the first clip, easing out from a
# slight zoom so it lands exactly on the clip's own framing.
LEAD_IN_SECONDS, LEAD_IN_ZOOM = 1.0, 0.06


def clip_frames(path):
    """All frames of a clip, plus its frame rate."""
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        return [frame.to_image() for frame in container.decode(stream)], float(stream.average_rate)


def push_in(still, centre_x, count, amount, label):
    """`count` vertical frames of a still with a slow zoom towards the face."""
    w, h = still.size
    cache, shots = {}, []
    for k in range(count):
        zoom = 1 + amount * k / count
        cw, ch = w / zoom, h / zoom
        left, top = (w - cw) * centre_x, (h - ch) * 0.25
        zoomed = still.resize((w, h), Image.BILINEAR, box=(left, top, left + cw, top + ch))
        shots.append(reframe(zoomed, centre_x, cache, label))
    return shots


def main():
    label = label_image()
    captions = {name: Image.open(HERE / "captions" / f"{name}.png").convert("RGBA")
                for *_, name, _ in BEATS}
    frames, sounds = [], []          # frames: finished vertical images; sounds: (name, start_s, samples)

    def add(image, caption=None):
        if caption is not None:
            image = image.copy()
            image.paste(caption, (0, CAPTION_Y), caption)
        frames.append(image)

    for clip, voice, centre_x, caption, pause in BEATS:
        cache = {}
        source, source_fps = clip_frames(HERE / "lipsync" / f"{clip}-raw.mp4")
        if not frames and LEAD_IN_SECONDS:
            frames += reversed(push_in(source[0], centre_x, round(LEAD_IN_SECONDS * FPS), LEAD_IN_ZOOM, label))
        samples = decode_mono(HERE / "audio" / f"{voice}.mp3")
        sounds.append((voice, len(frames) / FPS, samples))
        spoken = len(samples) / RATE
        count = round(len(source) / source_fps * FPS)       # the clip, resampled to 25 fps if need be
        shot = None
        for k in range(count):
            t = k / FPS
            shot = reframe(source[min(int(t * source_fps), len(source) - 1)], centre_x, cache, label)
            add(shot, captions[caption] if t < spoken else None)
        for _ in range(round(pause * FPS)):                 # hold the last frame for the pause
            add(shot)

    # Reaction: the furious wife with a slow push-in; a silent beat, then the laughter.
    samples = decode_mono(HERE / "audio" / f"{REACTION_SOUND}.mp3")
    sounds.append((REACTION_SOUND, len(frames) / FPS + REACTION_BEAT, samples))
    count = round((REACTION_BEAT + len(samples) / RATE + REACTION_TAIL) * FPS)
    still = Image.open(REACTION_STILL).convert("RGB")
    for k, image in enumerate(push_in(still, REACTION_X, count, 0.12, label)):
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
