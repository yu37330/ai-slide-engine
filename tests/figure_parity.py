"""独立した原典Pythonデモを実行し、同じ操作をJSON経由で再生成する。"""
import argparse
import functools
import importlib.util
import inspect
import json
import os
import runpy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"skills/ai-slide-engine/scripts"
sys.path.insert(0,str(ROOT))
import jfig
from aws_assets import configure
from build import figure_svg
from figure_palette import adaptive_svg
from template_render import cover_svg
PUBLIC={"T","R","C","L","A","icon","aws","bubble","think","box","frame","card","tag","head","num","ok","ng","warn","blocked","code"}
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def json_value(value):
    return json.loads(json.dumps(value,ensure_ascii=False))
def run(up,out,cache):
    out.mkdir(parents=True,exist_ok=False)
    src=up/"skills/marp-jinno/scripts"
    orig=module("upstream_jfig",src/"jfig.py")
    orig_cover=module("upstream_cover",src/"cover_art.py")
    orig_marks=module("upstream_marks",src/"marks.py")
    orig_palette=module("upstream_palette",up/"marp/scripts/figure_palette.py")
    if cache:
        configure(cache)
        orig._AWS=jfig._AWS
    old_class=orig.Fig
    methods={n:getattr(old_class,n) for n in PUBLIC}
    def record(f,name,func,args,kwargs):
        if f.depth==0:
            params=inspect.signature(func).bind(f,*args,**kwargs).arguments.copy()
            params.pop(next(iter(params)))
            if name=="aws":
                params["name"]=orig.aws_path(params["name"]).stem
            if params.get("aws"):
                params["aws"]=orig.aws_path(params["aws"]).stem
            f.operations.append({"component":name,"args":[],"kwargs":json_value(params)})
        f.depth+=1
        try:return func(f,*args,**kwargs)
        finally:f.depth-=1
    class Recorder(old_class):
        def __init__(self,width=1160,height=380,title=None):
            self.operations=[];self.depth=0;self.title=title
            super().__init__(width,height,title)
    def wrap(name,fn):
        @functools.wraps(fn)
        def call(self,*args,**kwargs):
            return record(self,name,fn,args,kwargs)
        return call
    for name,fn in methods.items():setattr(Recorder,name,wrap(name,fn))
    for name in ("facts","steps"):setattr(orig,name,wrap(name,getattr(orig,name)))
    orig.Fig=Recorder
    saved=sys.modules["jfig"];old_path=sys.path[:]
    try:
        sys.modules["jfig"]=orig
        demo=runpy.run_path(str(src/"jfig_demo.py"),run_name="parity_demo")
    finally:
        sys.modules["jfig"]=saved;sys.path[:]=old_path
    cases=[];covered=set()
    def compare(name,expected,actual,width,height,ops=None):
        expected=expected.encode() if isinstance(expected,str) else expected
        actual=actual.encode() if isinstance(actual,str) else actual
        assert expected==actual, name+" SVG bytes differ"
        for theme in ("petrol","paper"):
            a=expected if theme=="petrol" else orig_palette.adaptive_svg(expected)
            b=actual if theme=="petrol" else adaptive_svg(actual)
            assert a==b,name+" palette bytes differ"
            path=out/(name+"-"+theme);path.mkdir()
            (path/"original.svg").write_bytes(a);(path/"candidate.svg").write_bytes(b)
            cases.append({"id":name+"-"+theme,"width":width,"height":height})
        if ops:
            covered.update(op["component"] for op in ops)
            (out/(name+".json")).write_text(json.dumps(ops,ensure_ascii=False,indent=2),encoding="utf-8")
        print("FIGURE_BYTES_EXACT",name,flush=True)
    demos=["before","after","arch","announce","allow_deny","how_to"]
    for name in demos:
        if not cache and name in ("arch","announce","allow_deny"):continue
        f=demo[name]()
        cfg={"width":f.width,"height":f.height,"alt":f.title,"operations":f.operations}
        compare("demo-"+name,f.svg(),figure_svg(cfg),f.width,f.height,f.operations)
    # 全20メソッドとfacts/stepsの明示的な単独回帰。デモで未使用の機能も網羅。
    primitive={
        "T":([100,100,"座標"],{}),"R":([100,100,220,100],{"fill":"#edf4f6"}),
        "C":([200,150,30],{}),"L":([[[100,100],[300,100],[300,220]]],{"both":True,"dash":True}),
        "A":([100,160,400,160,"矢印"],{}),"icon":([180,80,"agent","Agent"],{}),
        "aws":([200,80,"Lambda","AWS Lambda"],{}),
        "bubble":([100,100,240,"質問",[400,220]],{}),"think":([100,100,240,"検討",[400,220]],{}),
        "box":([100,100,260,110,"処理","補足"],{"tone":"a"}),"frame":([100,100,550,200,"範囲"],{"dash":True}),
        "card":([100,100,300,160,"カード","本文"],{}),"tag":([100,100,"比較"],{}),
        "head":([100,100,"見出し",500],{}),"num":([200,150,1],{"ring":True}),
        "ok":([200,150],{}),"ng":([200,150],{}),"warn":([200,150],{}),
        "blocked":([[[100,150],[400,150]]],{"label":"拒否"}),
        "code":([100,60,500,["a = 1","print(a)"],"コード"],{"hl":[0]}),
        "facts":([40,100,1080,[["項目","値","補足"],["対象","例","説明"]]],{}),
        "steps":([40,100,[["準備","入力"],["実行","確認"]]],{"gap":100})
    }
    for name,(args,kwargs) in primitive.items():
        if name=="aws" and not cache:continue
        f=Recorder(1160,400,"Primitive "+name)
        if name in ("facts","steps"):getattr(orig,name)(f,*args,**kwargs)
        else:getattr(f,name)(*args,**kwargs)
        cfg={"width":f.width,"height":f.height,"alt":f.title,"operations":f.operations}
        compare("primitive-"+name,f.svg(),figure_svg(cfg),f.width,f.height,f.operations)
    # 全アイコン種類を独立原典で描画（名前・形・色を保持）。
    f=Recorder(1160,400,"All line icons")
    for i,name in enumerate(orig.SHAPES):
        f.icon(80+(i%7)*160,15+(i//7)*94,name,size=64)
    compare("all-line-icons",f.svg(),figure_svg({"width":1160,"height":400,"alt":f.title,"operations":f.operations}),1160,400,f.operations)
    # 旧marksは戻り値がSVG断片。原典の断片を直接並べた結果と比較。
    for name,fn,args in [
        ("mark_actor",orig_marks.actor,["user",200,70,68]),
        ("mark_label",orig_marks.label,[200,140,"旧ラベル"]),
        ("mark_speech",orig_marks.speech,[100,100,220,"質問",[400,220]])
    ]:
        f=old_class(1160,400,"Legacy "+name);f.parts.append(fn(*args))
        ops=[{"component":name,"args":args}]
        compare(name,f.svg(),figure_svg({"width":1160,"height":400,"alt":"Legacy "+name,"operations":ops}),1160,400,ops)
    # 表紙5部品。原典を直接呼んで比較。
    cover_ops=[
        {"component":"card","args":[45,80,210,120]},
        {"component":"block","args":[300,300,200,140]},
        {"component":"bar","args":[65,245,170]},
        {"component":"link","args":["M250 180 L350 280"]},
        {"component":"dot","args":[350,280]}
    ]
    ref=out/"reference-cover.svg";candidate=out/"candidate-cover.svg"
    orig_cover.save(ref,"Original cover",[getattr(orig_cover,o["component"])(*o["args"]) for o in cover_ops])
    actual=cover_svg({"title":"Original cover","operations":cover_ops},candidate)
    compare("cover",ref.read_bytes(),actual,560,720)
    expected=PUBLIC|{"facts","steps","mark_actor","mark_label","mark_speech"}
    if not cache:expected.remove("aws")
    assert expected<=covered,sorted(expected-covered)
    (out/"manifest.json").write_text(json.dumps({"cases":cases,"demo_count":len(demos) if cache else 3,"public_operations":sorted(covered),"line_icon_count":len(orig.SHAPES)},indent=2))
    print("FIGURE_PARITY_SUMMARY",json.dumps({"demos":len(demos) if cache else 3,"operations":len(covered),"icon_types":len(orig.SHAPES),"svg_cases":len(cases)}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("upstream",type=Path);p.add_argument("out",type=Path);p.add_argument("--aws-cache",type=Path,default=os.getenv("OFFICIAL_AWS_CACHE"))
    a=p.parse_args();run(a.upstream.resolve(),a.out,a.aws_cache)
