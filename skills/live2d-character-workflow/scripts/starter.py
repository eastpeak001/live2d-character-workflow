"""Generate an original paper mobile to try the full workflow without character art."""
import argparse
import json
from pathlib import Path
from shutil import copyfile
from PIL import Image, ImageDraw
from layers_psd import build
from motion_keys import make


def create(folder):
    folder.mkdir(parents=True,exist_ok=False)
    size=(320,384)
    def save_layer(name,draw):
        image=Image.new("RGBA",size)
        draw(ImageDraw.Draw(image))
        image.save(folder/(name+".png"))
        return {"name":name,"file":name+".png"}
    def stand(d):
        d.rounded_rectangle((49,315,259,332),radius=7,fill="#314553")
        d.rounded_rectangle((73,65,88,318),radius=6,fill="#4d7180")
        d.rounded_rectangle((73,64,221,77),radius=6,fill="#4d7180")
        d.ellipse((211,67,221,77),fill="#d5ac77")
    def ribbon(d):
        d.line([(216,74),(200,125),(205,167)],fill="#b07957",width=5)
    def jewel(d):
        d.polygon([(205,161),(239,201),(205,254),(171,201)],fill="#df7960",outline="#48384c",width=3)
        d.polygon([(205,170),(226,200),(205,238),(194,201)],fill="#edb17d")
        d.line([(181,201),(205,248),(231,201)],fill="#ac5159",width=2)
    parts=[save_layer("Stand",stand),save_layer("Ribbon",ribbon),save_layer("Pendant",jewel)]
    controls=[
      {"id":"ParamSwing","name":"Swing at the hanger","layers":["Ribbon"],"pivot":[.675,.19],"degrees":10,"grid":[5,8]},
      {"id":"ParamTip","name":"Pendant follow-through","parent":"ParamSwing","layers":["Pendant"],"pivot":[.64,.43],"degrees":5,"grid":[5,8]}]
    curve={"fps":48,"frames":96,"loop":True,"tracks":{
        "ParamSwing":{"keys":[[0,0],[24,1],[48,0],[72,-1],[96,0]]},
        "ParamTip":{"keys":[[0,-.4],[7,0],[31,1],[55,0],[79,-1],[96,-.4]]}}}
    def write(name,data):
        (folder/name).write_text(json.dumps(data,indent=2),"utf-8")
    write("layers.json",{"canvas":size,"layers":parts})
    write("rig.json",{"controls":controls})
    write("keys.json",curve)
    build(folder/"layers.json",folder/"Mobile.psd")
    write("Swing.motion3.json",make(curve))
    copyfile(Path(__file__).resolve().parents[1] / "assets" / "starter-neutral.cmo3",
             folder / "Neutral.cmo3")
    print("Practice layers, Mobile.psd, Neutral.cmo3 and Swing.motion3.json are ready.")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("new_folder",type=Path)
    create(p.parse_args().new_folder)
