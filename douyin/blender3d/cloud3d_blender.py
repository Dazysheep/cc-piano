"""后台 Blender 里运行（cloud3d.py 调用）：用 blender-mcp 插件里的 Hyper3D Rodin（官方站点模式）从图片生成
前后都完整的 3D 模型，导入后导出 model.glb、model.blend、thumb.png（和本地浮雕同样的文件）。
密钥从环境变量 BLENDERMCP_HYPER3D_API_KEY 读（插件自己支持），不写进任何文件。
用法：blender -b --factory-startup --python cloud3d_blender.py -- --dir <模型文件夹> --image <图片>
"""
import argparse
import math
import sys
import time
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--dir", type=Path, required=True)
ap.add_argument("--image", type=Path, required=True)
ap.add_argument("--timeout", type=int, default=900)
a = ap.parse_args(argv)
D = a.dir

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("blender_mcp_addon", default_set=True)
mod = sys.modules["blender_mcp_addon"]
scene = bpy.context.scene
scene.blendermcp_use_hyper3d = True
scene.blendermcp_hyper3d_mode = "MAIN_SITE"
srv = mod.BlenderMCPServer()

job = srv.create_rodin_job_main_site(images=[(a.image.suffix.lower(), a.image.read_bytes())])
if not isinstance(job, dict) or job.get("error") or "uuid" not in job:
    raise SystemExit(f"Hyper3D 建任务失败：{job}")
key, uuid = job["jobs"]["subscription_key"], job["uuid"]
print("cc-piano cloud job", uuid, flush=True)
t0 = time.time()
while True:
    st = srv.poll_rodin_job_status_main_site(key).get("status_list", [])
    print("cc-piano cloud status", st, flush=True)
    if st and all(s == "Done" for s in st):
        break
    if any(s == "Failed" for s in st):
        raise SystemExit("Hyper3D 生成失败")
    if time.time() - t0 > a.timeout:
        raise SystemExit("Hyper3D 等太久了（超过 %d 秒）" % a.timeout)
    time.sleep(6)
res = srv.import_generated_asset_main_site(uuid, D.name)
if not res.get("succeed", True) or not [o for o in scene.objects if o.type == "MESH"]:
    raise SystemExit(f"Hyper3D 下载 / 导入失败：{res}")

# 摆正：站在地面上、居中
meshes = [o for o in scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
for o in meshes:
    o.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
size = max(hi - lo)
bpy.ops.export_scene.gltf(filepath=str(D / "model.glb"), export_format="GLB", export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=str(D / "model.blend"), compress=True)

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = 512
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
h = hi.z - lo.z
cam.location = (size * 0.62, -size * 1.35, h * 0.72)
d = Vector((0, 0, h * 0.5)) - cam.location
cam.rotation_euler = (math.atan2(math.hypot(d.x, d.y), -d.z), 0, math.atan2(d.y, d.x) - math.pi / 2)
cam.data.lens = 45
scene.render.filepath = str(D / "thumb.png")
bpy.ops.render.render(write_still=True)
print("cc-piano cloud done:", D, flush=True)
