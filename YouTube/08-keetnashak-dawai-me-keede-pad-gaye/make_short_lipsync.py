"""Assemble the lip-synced Short (1080x1920, 25 fps).

A customer asks Sameer, who runs a pesticide shop, for insecticide; Sameer is
surprised because he bought some ten days ago; the customer complains that
insects have got into it (each line with its Hindi captions, which change as
the line is spoken); then the shot cuts to Sameer, baffled, with the laugh
track over him.

The scene art is drawn 4:5, so each frame fills the Short's window uncropped.

Run (from this folder):
    uv run --system-certs --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_short_lipsync.py
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from make_vertical_clip import RATE, WINDOW_H, WINDOW_W, WINDOW_Y, decode_mono, label_image, reframe

HERE = Path(__file__).parent
OUTPUT = HERE / "keetnashak-dawai-lipsync-short.mp4"
FPS = 25

# (talking clip, voice line, crop centre across the frame, captions, pause after the line)
# Captions are (card, second into the line at which it appears); the times sit in the
# pauses between phrases.
BEATS = [
    ("line1-customer", "line1", 0.5, [("line1a", 0.0), ("line1b", 2.05)], 0.30),
    ("line2-sameer", "line2", 0.5, [("line2a", 0.0), ("line2b", 2.50)], 0.30),
    ("line3-customer", "line3", 0.5, [("line3", 0.0)], 0.15),
]
# Reaction: still of the baffled Sameer, a silent beat, then the laugh track.
REACTION_STILL, REACTION_X, REACTION_BEAT, REACTION_SOUND, REACTION_TAIL = (
    HERE / "characters" / "sameer-puzzled.png", 0.53, 0.6, "laughter", 0.5)
CAPTION_Y = WINDOW_Y + WINDOW_H - 300
# Silent lead-in before the first line: the first frame of the first clip, easing out from a
# slight zoom so it lands exactly on the clip's own framing.
LEAD_IN_SECONDS, LEAD_IN_ZOOM = 1.0, 0.06
TRIM_TOP_SHARE = 0.25   # share of a too-tall clip's extra height that is cut from the top
# Held still per clip (a polygon in raw clip pixels), for anything the lip-sync model wrongly moves.
FREEZE = {}


def to_window(image):
    """Trim a frame to the window's 4:5 shape.

    The lip-sync model returns the 4:5 art as 3:4 (it trims the sides), so the extra height
    is cut here, mostly from the bottom, where the caption sits anyway.
    """
    w, h = image.size
    keep = round(w * WINDOW_H / WINDOW_W)
    if keep >= h:
        return image
    top = round((h - keep) * TRIM_TOP_SHARE)
    return image.crop((0, top, w, top + keep))


def clip_frames(path, freeze=None):
    """All frames of a clip (trimmed to 4:5), plus its frame rate.

    `freeze` is a polygon in the raw clip's pixels; inside it every frame shows the clip's
    first frame, which keeps a listener the lip-sync model also animated from mouthing along.
    """
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        frames, fps = [frame.to_image() for frame in container.decode(stream)], float(stream.average_rate)
    if freeze:
        mask = Image.new("L", frames[0].size, 0)
        ImageDraw.Draw(mask).polygon(freeze, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(14))
        frames = [Image.composite(frames[0], frame, mask) for frame in frames]
    return [to_window(frame) for frame in frames], fps


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
                for *_, cards, _ in BEATS for name, _ in cards}
    frames, sounds = [], []          # frames: finished vertical images; sounds: (name, start_s, samples)

    def add(image, caption=None):
        if caption is not None:
            image = image.copy()
            image.paste(caption, (0, CAPTION_Y), caption)
        frames.append(image)

    for clip, voice, centre_x, cards, pause in BEATS:
        cache = {}
        source, source_fps = clip_frames(HERE / "lipsync" / f"{clip}-raw.mp4", FREEZE.get(clip))
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
            card = [name for name, at in cards if at <= t][-1]
            add(shot, captions[card] if t < spoken else None)
        for _ in range(round(pause * FPS)):                 # hold the last frame for the pause
            add(shot)

    # Reaction: the baffled Sameer with a slow push-in; a silent beat, then the laughter.
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
