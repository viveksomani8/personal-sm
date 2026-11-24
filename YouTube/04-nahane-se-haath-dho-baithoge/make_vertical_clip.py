"""Reframe a landscape talking-head clip as a vertical Short segment (1080x1920).

The speaker is cut out as a 4:5 window from the 16:9 clip and shown large, over
a blurred, darkened copy of the same frame, with the channel name on top. The
audio comes from the given clip file (the original voice line), so sync is
exactly what the lip-sync model was given.

Usage:
    uv run --no-project --python 3.12 --with av --with pillow --with numpy \
        python make_vertical_clip.py <talking_clip.mp4> <voice_line.mp3> <output.mp4> [centre_x]

centre_x is where the face sits across the source frame, 0..1 (default 0.5).
"""

import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, RATE = 1080, 1920, 44100
CHANNEL = "Jokes Apart"
WINDOW_W, WINDOW_H = 1080, 1350   # the 4:5 window the speaker is shown in
WINDOW_Y = 330


def label_image():
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 64)
    box = font.getbbox(CHANNEL)
    image = Image.new("RGBA", (box[2] + 40, box[3] + 30), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((22, 12), CHANNEL, font=font, fill=(0, 0, 0, 160))
    draw.text((20, 10), CHANNEL, font=font, fill=(255, 214, 77, 255))
    return image


def reframe(frame, centre_x, backdrop_cache, label):
    """One vertical frame from one landscape source frame."""
    src_w, src_h = frame.size
    crop_w = src_h * WINDOW_W / WINDOW_H
    left = min(max(centre_x * src_w - crop_w / 2, 0), src_w - crop_w)
    window = frame.resize((WINDOW_W, WINDOW_H), Image.LANCZOS, box=(left, 0, left + crop_w, src_h))
    if "image" not in backdrop_cache:               # the backdrop barely changes: build it once
        scale = H / src_h * 1.15
        big = frame.resize((round(src_w * scale), round(src_h * scale)), Image.BICUBIC)
        x, y = (big.width - W) // 2, (big.height - H) // 2
        blurred = big.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(30))
        backdrop_cache["image"] = ImageEnhance.Brightness(blurred).enhance(0.4)
    out = backdrop_cache["image"].copy()
    out.paste(window, (0, WINDOW_Y))
    draw = ImageDraw.Draw(out)
    draw.rectangle([0, WINDOW_Y - 6, W, WINDOW_Y - 1], fill="white")
    draw.rectangle([0, WINDOW_Y + WINDOW_H, W, WINDOW_Y + WINDOW_H + 5], fill="white")
    out.paste(label, ((W - label.width) // 2, 130), label)
    return out


def decode_mono(path):
    resampler = av.AudioResampler(format="s16", layout="mono", rate=RATE)
    parts = []
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            parts += [r.to_ndarray().ravel() for r in resampler.resample(frame)]
        parts += [r.to_ndarray().ravel() for r in resampler.resample(None)]
    return np.concatenate(parts)


def main(clip, voice, output, centre_x=0.5):
    centre_x, label, cache = float(centre_x), label_image(), {}
    pcm = decode_mono(voice)
    with av.open(str(clip)) as src, av.open(str(output), "w") as out:
        v_in = src.streams.video[0]
        fps = v_in.average_rate
        video = out.add_stream("libx264", rate=fps)
        video.width, video.height, video.pix_fmt = W, H, "yuv420p"
        video.options = {"crf": "18", "preset": "medium"}
        audio = out.add_stream("aac", rate=RATE, layout="mono")
        to_aac = av.AudioResampler(format="fltp", layout="mono", rate=RATE)

        frames = 0
        for frame in src.decode(v_in):
            image = reframe(frame.to_image(), centre_x, cache, label)
            out.mux(video.encode(av.VideoFrame.from_image(image)))
            frames += 1
        out.mux(video.encode(None))

        for i in range(0, len(pcm), 1024):
            chunk = av.AudioFrame.from_ndarray(pcm[i:i + 1024].reshape(1, -1), format="s16", layout="mono")
            chunk.sample_rate, chunk.pts = RATE, i
            for resampled in to_aac.resample(chunk):
                out.mux(audio.encode(resampled))
        out.mux(audio.encode(None))
    print(f"{Path(output).name}: {frames} frames at {float(fps):.2f} fps, voice {len(pcm) / RATE:.2f}s")


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
