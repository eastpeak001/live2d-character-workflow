"""Add independent, nested warp controls to a fresh PSD import saved by Cubism 5."""
import argparse
from copy import deepcopy
from itertools import count
import json
import math
import os
from pathlib import Path
import re
from uuid import uuid4
import xml.etree.ElementTree as ET

from cubism_archive import Archive

ASSETS = Path(__file__).resolve().parents[1] / "assets"
WARP_CLASSES = (
    "deformer.ACDeformerForm", "deformer.ACDeformerSource",
    "deformer.warp.CWarpDeformerForm", "deformer.warp.CWarpDeformerSource",
    "id.CDeformerId", "interpolator.InterpolationType", "interpolator.KeyOnParameter",
    "interpolator.KeyformBindingSource",
    "interpolator.extendedInterpolation.ExtendedInterpolationType",
)


def field(node, name):
    return next(child for child in node if child.get("xs.n") == name)


def set_ref(node, identity):
    node.set("xs.ref", identity)


def append(array, node):
    array.append(node)
    array.set("count", str(len(array)))


def points_text(node, points):
    values = [f"{n:.10g}" for pair in points for n in pair]
    node.text = " ".join(values)
    node.set("count", str(len(values)))


def warp_points(spec, size, grid, key, local):
    width, height = size
    cols, rows = grid
    px, py = spec.get("pivot", [.5, .5])
    mx, my = spec.get("move", [0, 0])
    sx, sy = spec.get("stretch", [0, 0])
    angle = math.radians(key * spec.get("degrees", 0))
    falloff = spec.get("weight_y")
    if falloff and falloff[0] == falloff[1]:
        raise ValueError("weight_y needs two distinct normalized heights.")
    for j in range(rows+1):
        y = j / rows
        weight = 1.0
        if falloff:
            u = min(1., max(0., (y-falloff[0])/(falloff[1]-falloff[0])))
            weight = u*u*(3.-2.*u)
        for i in range(cols+1):
            x = i / cols
            dx = (x-px)*width*(1.+key*sx)
            dy = (y-py)*height*(1.+key*sy)
            tx = px*width + math.cos(angle)*dx - math.sin(angle)*dy + key*mx*width
            ty = py*height + math.sin(angle)*dx + math.cos(angle)*dy + key*my*height
            u = x + weight*(tx/width-x)
            v = y + weight*(ty/height-y)
            yield (u, v) if local else (u*width, v*height)


def bind(source, specs, output, psd=None):
    if output.exists() or output.suffix.lower() != ".cmo3":
        raise ValueError("Choose a new .cmo3 output path.")
    if source.parent.resolve() != output.parent.resolve() and psd is None:
        raise ValueError("Provide --psd to relink a project written to another folder.")
    if psd and not psd.is_file():
        raise ValueError("The requested PSD does not exist.")
    archive = Archive(source.read_bytes())
    raw = archive.xml()
    root = ET.fromstring(raw)
    shared, model = root.find("shared"), root.find("main")[0]
    items = {n.get("xs.id"): n for n in shared}
    ids = count(1+max(int(k[1:]) for k in items if k and k.startswith("#")))
    def register(obj):
        identity = "#" + str(next(ids))
        obj.set("xs.id", identity)
        shared.append(obj)
        items[identity] = obj
        return identity

    def guid(kind, name):
        return register(ET.Element(kind, {"note": name, "uuid": str(uuid4())}))

    root_part = items[field(model,"rootPart").get("xs.ref")]
    root_part_id = field(root_part,"guid").get("xs.ref")
    root_target = next(k for k,n in items.items() if n.tag=="CDeformerGuid" and n.get("note")=="ROOT")
    coord = {field(n,"coordName").text: k for k,n in items.items() if n.tag=="CoordType"}
    if "DeformerLocal" not in coord:
        item = ET.Element("CoordType")
        ET.SubElement(item, "s", {"xs.n":"coordName"}).text = "DeformerLocal"
        coord["DeformerLocal"] = register(item)
    canvas = field(model, "canvas")
    size = [int(field(canvas,k).text) for k in ("pixelWidth","pixelHeight")]
    meshes = {m.find(".//CDrawableId").get("idstr"):m for m in shared.findall("CArtMeshSource")}
    params = field(field(model,"parameterSourceSet"),"_sources")
    group = items[field(model,"rootParameterGroup").get("xs.ref")]
    used = {n.get("idstr") for n in shared.findall("CParameterId")}
    targets = {}
    template_warp, template_grid, template_binding = list(ET.parse(ASSETS/"warp.xml").getroot())
    if not specs or not len(params):
        raise ValueError("A rig recipe and a neutral import with default parameters are required.")
    for spec in specs:
        ident, name = spec["id"], spec["name"]
        if ident in used or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", ident):
            raise ValueError(f"Parameter ID is invalid or already in use: {ident}")
        used.add(ident)
        parent = spec.get("parent")
        if parent and parent not in targets:
            raise ValueError(f"Declare parent control {parent} before {ident}.")
        grid = spec.get("grid", [6, 10])
        if len(grid)!=2 or any(type(n) is not int or not 1<=n<=64 for n in grid):
            raise ValueError("grid requires two integers in 1..64")
        param = deepcopy(params[0])
        param_guid = guid("CParameterGuid", ident)
        set_ref(field(param,"id"), register(ET.Element("CParameterId", {"idstr":ident})))
        set_ref(field(param,"guid"), param_guid)
        set_ref(field(param,"parentGroupGuid"), field(group,"guid").get("xs.ref"))
        for k, v in {"name":name,"description":"","minValue":"-1","maxValue":"1","defaultValue":"0","isRepeat":"false"}.items():
            field(param,k).text = v
        append(params,param)
        append(field(group,"_childGuids"),ET.Element("CParameterGuid",{"xs.ref":param_guid}))
        warp, keygrid, binding = [deepcopy(x) for x in (template_warp,template_grid,template_binding)]
        warp_guid = guid("CDeformerGuid", "Warp"+ident)
        targets[ident] = warp_guid
        wid, gid, bid = [register(x) for x in (warp,keygrid,binding)]
        base = field(warp,"super")
        control = field(base,"super")
        field(control,"localName").text = name
        set_ref(field(control,"parentGuid"),root_part_id)
        set_ref(field(control,"keyformGridSource"),gid)
        set_ref(field(base,"guid"),warp_guid)
        field(base,"id").set("idstr","Warp"+ident)
        set_ref(field(base,"targetDeformerGuid"),targets[parent] if parent else root_target)
        field(warp,"col").text,field(warp,"row").text = map(str,grid)
        set_ref(field(keygrid,"keyformBindings")[0],bid)
        set_ref(field(binding,"_gridSource"),gid)
        set_ref(field(binding,"parameterGuid"),param_guid)
        field(binding,"description").text = name
        forms, knots = field(warp,"keyforms"), field(keygrid,"keyformsOnGrid")
        form_proto, knot_proto = forms[0], knots[0]
        forms.remove(form_proto)
        knots.remove(knot_proto)
        for index,value in enumerate((-1,0,1)):
            form,knot = deepcopy(form_proto),deepcopy(knot_proto)
            fid = guid("CFormGuid", ident+" "+str(value))
            set_ref(form.find(".//CFormGuid"),fid)
            set_ref(form.find(".//CWarpDeformerSource"),wid)
            set_ref(form.find(".//CoordType"),coord["DeformerLocal" if parent else "Canvas"])
            points_text(field(form,"positions"),warp_points(spec,size,grid,value,bool(parent)))
            set_ref(knot.find(".//CFormGuid"),fid)
            set_ref(knot.find(".//KeyformBindingSource"),bid)
            knot.find(".//i").text=str(index)
            append(forms,form)
            append(knots,knot)
        append(field(field(model,"deformerSourceSet"),"_sources"),ET.Element("CWarpDeformerSource",{"xs.ref":wid}))
        append(field(root_part,"_childGuids"),ET.Element("CDeformerGuid",{"xs.ref":warp_guid}))
        for mesh_id in spec.get("layers",[]):
            if mesh_id not in meshes:
                raise ValueError(f"Unknown ArtMesh {mesh_id!r}. Available IDs: {', '.join(meshes)}")
            mesh = meshes[mesh_id]
            target = mesh.find(".//CDeformerGuid[@xs.n='targetDeformerGuid']")
            if target.get("xs.ref") != root_target:
                raise ValueError(f"{mesh_id} is already attached. Assign a layer only to its innermost warp.")
            set_ref(target,warp_guid)
            for form in mesh.iter("CArtMeshForm"):
                space = form.find(".//CoordType[@xs.n='coordType']")
                if space.get("xs.ref") != coord["Canvas"]:
                    raise ValueError(f"Unexpected existing coordinate system for {mesh_id}.")
                arr=field(form,"positions")
                nums = list(map(float,arr.text.split()))
                points_text(arr,zip((x/size[0] for x in nums[::2]),(y/size[1] for y in nums[1::2])))
                set_ref(space,coord["DeformerLocal"])
    field(model,"name").text=output.stem
    if psd:
        sources = list(root.findall(".//file[@xs.n='psdFile']"))
        if len({item.text for item in sources}) != 1:
            raise ValueError("Relinking requires one source PSD.")
        for item in sources:
            item.text = Path(os.path.relpath(psd, output.parent)).as_posix()
    for i,n in enumerate(root.iter()):
        if n.get("xs.id"):
            n.set("xs.idx",str(i))
        if "xs.ref" in n.attrib and n.get("xs.ref") not in items:
            raise ValueError("Unresolved native object reference.")
    header = raw.split(b"<root", 1)[0]
    for class_name in WARP_CLASSES:
        statement = f"<?import com.live2d.cubism.doc.model.{class_name}?>".encode("ascii")
        if statement not in header:
            header += statement + b"\n"
    result = archive.with_xml(header + ET.tostring(root, encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as dest:
        dest.write(result)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("neutral",type=Path)
    p.add_argument("rig",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--psd",type=Path)
    args=p.parse_args()
    bind(args.neutral,json.loads(args.rig.read_text("utf-8"))["controls"],args.output,args.psd)
