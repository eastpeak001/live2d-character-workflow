"""Composite a numbered transparent Cubism PNG sequence over a still at a fixed scale."""
import argparse
import math
import os
import re
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageColor


def frames_in(folder, pattern):
    files = list(folder.glob(pattern))
    if not files:
        raise ValueError(f"No frames matching {pattern} in {folder}")
    numbered = []
    for item in files:
        match = re.fullmatch(r"(.*?)(\d+)", item.stem)
        if not match:
            raise ValueError(f"Expected a numbered PNG: {item.name}")
        numbered.append((match[1], int(match[2]), item))
    numbered.sort()
    prefix, first, _ = numbered[0]
    for offset, (label, number, _) in enumerate(numbered):
        if label != prefix or number != first + offset:
            raise ValueError("Use one sequence with consecutive, unique frame numbers.")
    return [row[2] for row in numbered]


def make_background(path, size, color, width, bottom):
    with Image.open(path) as src:
        art = src.convert("RGBA")
    opaque = art.getchannel("A").point(lambda v: 255 if v >= 64 else 0).getbbox()
    if not opaque:
        raise ValueError("Background art is empty.")
    art = art.crop(opaque)
    scale = size[0] * width / art.width
    art = art.resize((round(art.width * scale), max(1, round(art.height * scale))), Image.Resampling.LANCZOS)
    plate = Image.new("RGBA", size, ImageColor.getrgb(color))
    plate.alpha_composite(art, ((size[0] - art.width) // 2, round(size[1] * bottom) - art.height))
    return plate


def flatten(path, plate, size, height, center_x, top):
    with Image.open(path) as im:
        if im.size != size or "A" not in im.getbands():
            raise ValueError(f"Canvas size or alpha channel changed: {path.name}")
        frame = im.convert("RGBA")
        scale = height * plate.height / size[1]
        target = (max(1, round(size[0] * scale)), max(1, round(size[1] * scale)))
        frame = frame.resize(target, Image.Resampling.LANCZOS)
    surface = plate.copy()
    surface.alpha_composite(frame, (round(plate.width * center_x - target[0] / 2), round(plate.height * top)))
    return surface.convert("RGB")


def render(args):
    seq = frames_in(args.frames, args.pattern)
    speed, source_fps, output_fps = map(Fraction, [args.speed, args.fps, args.output_fps])
    if min(speed, source_fps, output_fps, args.loops, args.width, args.height, args.character_height, args.background_width) <= 0:
        raise ValueError("Sizes, rates and loop count must be positive.")
    if args.width % 2 or args.height % 2:
        raise ValueError("H.264 yuv420p needs even width and height.")
    if args.output.exists():
        raise FileExistsError(args.output)
    with Image.open(seq[0]) as first:
        size = first.size
    if args.expect is not None and len(seq) != args.expect:
        raise ValueError(f"Expected {args.expect} source frames, found {len(seq)}.")
    plate = make_background(args.background, (args.width, args.height), args.base_color, args.background_width, args.background_bottom)
    count = math.ceil(len(seq) * args.loops * output_fps / (source_fps * speed))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.output.parent, suffix=".mp4", delete=False) as tmp:
        pending = Path(tmp.name)
    try:
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{args.width}x{args.height}", "-framerate", str(output_fps), "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-threads", "4", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-vf", "scale=out_color_matrix=bt709", "-colorspace", "bt709", "-color_primaries", "bt709",
               "-color_trc", "bt709", "-movflags", "+faststart", str(pending)]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            previous = None
            for i in range(count):
                index = int(i * source_fps * speed / output_fps) % len(seq)
                if index != previous:
                    picture = flatten(seq[index], plate, size, args.character_height, args.center_x, args.character_top)
                    data = picture.tobytes()
                    previous = index
                process.stdin.write(data)
            process.stdin.close()
            if process.wait():
                raise RuntimeError("FFmpeg failed to encode the video.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        os.replace(pending, args.output)
    finally:
        pending.unlink(missing_ok=True)
    print(f"{args.output.name}: {len(seq)} source frames, {count} output frames at {output_fps} fps, {speed}x")


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("frames", type=Path)
    p.add_argument("background", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--pattern", default="*.png")
    p.add_argument("--fps", required=True, help="Native timeline rate, e.g. 48")
    p.add_argument("--expect", type=int, help="Expected native frame count")
    p.add_argument("--speed", default="1")
    p.add_argument("--loops", type=int, default=1)
    p.add_argument("--output-fps", default="60")
    p.add_argument("--width", type=int, default=864)
    p.add_argument("--height", type=int, default=1440)
    p.add_argument("--base-color", default="#321c2b")
    p.add_argument("--background-width", type=float, default=1.06, help="Width of opaque scenery / canvas width")
    p.add_argument("--background-bottom", type=float, default=1.02)
    p.add_argument("--character-height", type=float, default=.94, help="Height of the complete character canvas / video height")
    p.add_argument("--character-top", type=float, default=.025)
    p.add_argument("--center-x", type=float, default=.5)
    return p


if __name__ == "__main__":
    render(parser().parse_args())
