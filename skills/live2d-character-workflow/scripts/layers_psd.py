"""Assemble a registered, bottom-to-top stack of RGBA patches or original-art masks."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer


def build(manifest, output):
    data = json.loads(manifest.read_text("utf-8-sig"))
    size = tuple(data["canvas"])
    if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
        raise ValueError("canvas requires two positive pixel dimensions")
    if not data["layers"] or output.exists():
        raise ValueError("Supply layers and choose a new PSD output path.")
    document = PSDImage.new("RGBA", size, color=(0,0,0,0))
    source = None
    if "source" in data:
        with Image.open(manifest.parent / data["source"]) as im:
            source = im.convert("RGBA")
        if source.size != size:
            raise ValueError("Source art must match the design canvas.")
    names = set()
    for layer in data["layers"]:
        name = layer["name"]
        if not name or name in names:
            raise ValueError(f"Empty or duplicate layer name: {name!r}")
        names.add(name)
        if ("file" in layer) == ("mask" in layer):
            raise ValueError(f"Specify one file or one source mask for {name}.")
        if "file" in layer:
            with Image.open(manifest.parent / layer["file"]) as im:
                art = im.convert("RGBA")
            x,y = layer.get("xy", [0,0])
        else:
            if source is None or "xy" in layer:
                raise ValueError("Masks require a registered source on the full canvas.")
            with Image.open(manifest.parent / layer["mask"]) as im:
                mask = im.convert("L")
            if mask.size != size:
                raise ValueError("Mask size differs from the original.")
            art = source.copy()
            art.putalpha(ImageChops.multiply(source.getchannel("A"), mask))
            x,y = 0,0
        box = art.getchannel("A").getbbox()
        if box is None:
            raise ValueError(f"Layer {name} is empty.")
        left,top = x+box[0],y+box[1]
        if left<0 or top<0 or x+box[2]>size[0] or y+box[3]>size[1]:
            raise ValueError(f"Painted pixels of {name} lie outside the canvas.")
        pixel = PixelLayer.frompil(art.crop(box),document,name=name,top=top,left=left)
        pixel.visible = layer.get("visible",True)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("xb") as stream:
        document.save(stream)
    layers=PSDImage.open(output)
    if [x.name for x in layers] != [x["name"] for x in data["layers"]]:
        raise RuntimeError("Unexpected PSD layer order.")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("output",type=Path)
    args=p.parse_args()
    build(args.manifest,args.output)
