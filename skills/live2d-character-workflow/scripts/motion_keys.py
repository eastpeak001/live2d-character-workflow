"""Build an importable Cubism motion3 from frame-indexed tracks with periodic tangents."""
import argparse
import json
import math
from pathlib import Path


def make(data):
    fps, duration = data["fps"], data["frames"]
    if not isinstance(duration,int) or duration < 1 or not math.isfinite(fps) or fps <= 0:
        raise ValueError("Supply a positive frame count and frame rate.")
    loop=data.get("loop",True)
    curves=[]
    total_points=total_segments=0
    for name,track in data["tracks"].items():
        pts=track["keys"]
        if len(pts)<2 or pts[0][0]!=0 or pts[-1][0]!=duration:
            raise ValueError(f"{name}: include endpoint keys at 0 and frames.")
        if loop and pts[0][1]!=pts[-1][1]:
            raise ValueError(f"{name}: enter the same value at both ends of a loop.")
        if any(type(f) is not int or not math.isfinite(v) for f,v in pts) or any(a[0]>=b[0] for a,b in zip(pts,pts[1:])):
            raise ValueError(f"{name}: keys must be finite and strictly ordered.")
        mode=track.get("interpolation","smooth")
        if mode not in ("smooth","linear","stepped"):
            raise ValueError(f"{name}: unknown interpolation {mode}")
        slopes=[(b[1]-a[1])/(b[0]-a[0]) for a,b in zip(pts,pts[1:])]
        def tangent(i):
            if not loop and i in (0,len(pts)-1):
                return slopes[0] if i==0 else slopes[-1]
            a,b=slopes[(i-1)%len(slopes)],slopes[i%len(slopes)]
            return 2*a*b/(a+b) if a*b>0 else 0.0
        segments=[0.,pts[0][1]]
        total_points+=1
        for i,((f,v),(g,w)) in enumerate(zip(pts,pts[1:])):
            if mode=="smooth":
                h=(g-f)/3
                segments.extend([1,(f+h)/fps,v+tangent(i)*h,(g-h)/fps,w-tangent(i+1)*h,g/fps,w])
                total_points+=3
            else:
                segments.extend([0 if mode=="linear" else 2,g/fps,w])
                total_points+=1
            total_segments+=1
        curves.append({"Target":"Parameter","Id":name,"Segments":[round(v,9) for v in segments]})
    if not curves:
        raise ValueError("At least one parameter track is required.")
    return {"Version":3,"Meta":{"Duration":duration/fps,"Fps":fps,"Loop":loop,"AreBeziersRestricted":True,
            "CurveCount":len(curves),"TotalSegmentCount":total_segments,"TotalPointCount":total_points,
            "UserDataCount":0,"TotalUserDataSize":0},"Curves":curves,"UserData":[]}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("recipe",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    motion=make(json.loads(a.recipe.read_text("utf-8-sig")))
    a.output.parent.mkdir(exist_ok=True,parents=True)
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(motion,f,indent=2,allow_nan=False)
