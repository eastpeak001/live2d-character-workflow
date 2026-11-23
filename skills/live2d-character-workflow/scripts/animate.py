"""Put frame-based parameter keys on a new copy of a one-model Cubism scene."""
import argparse
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from bind_model import field
from cubism_archive import Archive
from motion_keys import make


def native_point(frame, value, before, after):
    def child(parent, tag, name, text):
        ET.SubElement(parent, tag, {"xs.n": name}).text = str(text)

    result = ET.Element("CBezierPt")
    anchor = ET.SubElement(result, "CSeqPt", {"xs.n": "anchor"})
    child(anchor, "b", "isCorner", "false")
    child(anchor, "i", "pos", frame)
    child(anchor, "d", "doubleValue", value)
    for name, (time, control_value) in (("next", after), ("prev", before)):
        handle = ET.SubElement(result, "CBezierCtrlPt", {"xs.n": name})
        child(handle, "f", "posF", round(time, 8))
        child(handle, "i", "pos", 0)
        child(handle, "d", "doubleValue", control_value)
        child(handle, "b", "isPosOptimized", "false")
    return result


def write_track(attr, recipe, curve, fps):
    data = field(attr, "valueData")
    seq = field(data, "super")
    positions = field(seq, "keyPts2")
    points, types = field(data, "points"), field(data, "curveTypes")
    if len(points):
        raise ValueError("Use a neutral scene with empty target parameter tracks.")
    keys = recipe["keys"]
    values = [value for _, value in keys]
    low, high = (float(field(attr, name).text) for name in ("rangeMin", "rangeMax"))
    if min(values) < low or max(values) > high:
        raise ValueError(f"{curve['Id']} has keys outside the model range {low} to {high}.")
    mode = recipe.get("interpolation", "smooth")
    kind = {"smooth": "SMOOTH", "stepped": "STEP", "linear": "LINEAR"}[mode]
    before, after = list(keys), list(keys)
    if mode == "smooth":
        segments = curve["Segments"]
        for i in range(len(keys)-1):
            segment = segments[2+i*7:2+(i+1)*7]
            after[i] = (segment[1]*fps, segment[2])
            before[i+1] = (segment[3]*fps, segment[4])
    for i, (frame, value) in enumerate(keys):
        points.append(native_point(frame, value, before[i], after[i]))
        types.append(ET.Element("CCurveType", {"v": kind}))
    positions.text = " ".join(str(f) for f, _ in keys)
    for node in (points, types, positions):
        node.set("count", str(len(keys)))
    for name, value in {"curMin":min(values), "curMax":max(values), "keyMin":keys[0][0],
                        "keyMax":keys[-1][0], "lastValue":values[0], "lastPos":0}.items():
        field(seq, name).text = str(value)


def animate(timeline, model, recipe, output):
    if output.exists() or output.suffix.lower() != ".can3":
        raise ValueError("Choose a new .can3 output path.")
    archive = Archive(timeline.read_bytes())
    raw = archive.xml()
    doc = ET.fromstring(raw)
    sources = doc.find("shared")
    scenes = sources.findall("CSceneSource")
    files = doc.findall(".//file[@xs.n='srcFile']")
    if len(scenes) != 1 or len(files) != 1 or len(sources.findall("CMvTrack_Live2DModel_Source")) != 1:
        raise ValueError("Use a new one-scene timeline containing only the matching model.")
    model_doc = ET.fromstring(Archive(model.read_bytes()).xml())
    objects = {node.get("xs.id"): node for node in model_doc.find("shared")}
    parameters = {}
    for param in model_doc.iter("CParameterSource"):
        guid = objects[field(param, "guid").get("xs.ref")].get("uuid")
        ident = objects[field(param, "id").get("xs.ref")].get("idstr")
        parameters[ident] = guid

    animation = sources.find("CAnimation")
    field(animation, "name").text = output.stem
    field(animation, "file").text = output.name
    files[0].text = Path(os.path.relpath(model, output.parent)).as_posix()
    resource = next(parent for parent in doc.iter() if files[0] in list(parent))
    field(resource, "name").text = model.name
    scene = scenes[0]
    field(scene, "sceneName").text = recipe.get("name", output.stem)
    motion = make(recipe)
    fps, length = recipe["fps"], recipe["frames"]
    movie = field(scene, "movieInfo")
    for name, value in {"duration":length, "workspaceStart":0, "workspaceEnd":length-1,
                        "fps":fps, "isLoopMotion":str(motion["Meta"]["Loop"]).lower()}.items():
        field(movie, name).text = str(value)
    for track in sources:
        if track.tag.startswith("CMvTrack_"):
            for limit in track.findall(".//i[@xs.n='duration']"):
                limit.text = str(length+1)

    tracks = {}
    for attr in sources.findall("CMvAttrF"):
        identity = attr.find(".//CParameterId")
        if identity is None:
            continue
        ident = identity.get("idstr")
        if ident not in parameters:
            raise ValueError(f"Timeline parameter {ident} is missing from the model.")
        field(field(attr, "super"), "guid").set("uuid", parameters[ident])
        tracks[ident] = attr
    for curve in motion["Curves"]:
        ident = curve["Id"]
        if ident not in tracks:
            raise ValueError(f"Add the model with parameter {ident} to the neutral timeline.")
        write_track(tracks[ident], recipe["tracks"][ident], curve, fps)

    header = raw.split(b"<root", 1)[0]
    statements = [b"<?version CBezierCtrlPt:2?>"]
    for name in ("CSeqPt", "CBezierCtrlPt", "CBezierPt"):
        statements.append(f"<?import com.live2d.cubism.doc.animation.movie.effect.attr.value.{name}?>".encode())
    for statement in statements:
        if statement not in header:
            header += statement + b"\n"
    for i, node in enumerate(doc.iter()):
        if "xs.idx" in node.attrib:
            node.set("xs.idx", str(i))
    blob = archive.with_xml(header + ET.tostring(doc, encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(blob)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("keys", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    animate(args.timeline, args.model, json.loads(args.keys.read_text("utf-8-sig")), args.output)
