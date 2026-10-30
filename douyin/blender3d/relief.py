"""后台 Blender 里运行（image2mesh.py 调用）：抠好的图 + 深度图 → 有厚度的立体浮雕模型。

坐标：模型竖着站在地面上（Z 朝上，底边在 Z=0），正面朝 -Y（Blender 的前视图方向），高 2 米、宽按图片比例；
深度越近越往 -Y 凸出。抠图透明的地方不生成面。贴图是抠好的原图（带透明度），UV 就是图片坐标。
加厚（Solidify）和平滑后应用修改器，导出 model.glb（贴图内嵌）、model.blend、thumb.png（Workbench 快速渲染）。
用法：blender -b --factory-startup --python relief.py -- --dir <模型文件夹> [--strength 0.35] [--thickness 0.04]
"""
import argparse
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--dir", type=Path, required=True)
ap.add_argument("--strength", type=float, default=0.35)
ap.add_argument("--thickness", type=float, default=0.04)
ap.add_argument("--res", type=int, default=220)          # 长边的网格格数
a = ap.parse_args(argv)
D = a.dir

bpy.ops.wm.read_factory_settings(use_empty=True)
cut = bpy.data.images.load(str(D / "cutout.png"))
dep = bpy.data.images.load(str(D / "depth.png"))
w, h = cut.size
rgba = np.array(cut.pixels[:], np.float32).reshape(h, w, 4)[::-1]          # Blender 的像素从下往上：翻成从上往下
depth = np.array(dep.pixels[:], np.float32).reshape(dep.size[1], dep.size[0], 4)[::-1][..., 0]

# 网格：长边 res 格
if w >= h:
    nx, ny = a.res, max(2, round(a.res * h / w))
else:
    nx, ny = max(2, round(a.res * w / h)), a.res
H = 2.0
W = H * w / h
xs = np.linspace(0, w - 1, nx + 1).round().astype(int)
ys = np.linspace(0, h - 1, ny + 1).round().astype(int)
alpha = rgba[np.ix_(ys, xs)][..., 3]
dz = depth[np.ix_(ys, xs)]
inside = alpha > 0.5

bm = bmesh.new()
uv = bm.loops.layers.uv.new("UVMap")
verts = {}
for j in range(ny + 1):
    for i in range(nx + 1):
        if not inside[j, i]:
            continue
        u, v = i / nx, j / ny
        verts[j, i] = bm.verts.new(((u - 0.5) * W, -dz[j, i] * a.strength * H * 0.5, (1 - v) * H))
for j in range(ny):
    for i in range(nx):
        q = [(j, i), (j, i + 1), (j + 1, i + 1), (j + 1, i)]
        if all(k in verts for k in q):
            f = bm.faces.new([verts[k] for k in q])
            for loop, (jj, ii) in zip(f.loops, q):
                loop[uv].uv = (ii / nx, 1 - jj / ny)
if not bm.faces:
    raise SystemExit("抠图后没有可用的面")
mesh = bpy.data.meshes.new("relief")
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new(D.name, mesh)
bpy.context.scene.collection.objects.link(obj)
for p in mesh.polygons:
    p.use_smooth = True

# 材质：抠好的原图（带透明度）
mat = bpy.data.materials.new("relief")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = cut
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
bsdf.inputs["Roughness"].default_value = 0.65
mat.blend_method = "CLIP" if hasattr(mat, "blend_method") else mat.blend_method
mesh.materials.append(mat)

# 平滑 + 加厚，然后应用修改器
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
sm = obj.modifiers.new("smooth", "SMOOTH")
sm.factor, sm.iterations = 0.5, 4
so = obj.modifiers.new("thick", "SOLIDIFY")
so.thickness, so.offset = a.thickness * H, 1.0
for m in list(obj.modifiers):
    bpy.ops.object.modifier_apply(modifier=m.name)
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
obj.location = (0, 0, 0)
bpy.context.view_layer.update()
zmin = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
obj.location.z -= zmin                                                      # 站在地面上

# 导出
cut.pack()
bpy.ops.export_scene.gltf(filepath=str(D / "model.glb"), export_format="GLB", use_selection=False,
                          export_image_format="AUTO", export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=str(D / "model.blend"), compress=True)

# 缩略图：Workbench（快，不吃显卡），正面偏右上 3/4 视角，透明背景
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "TEXTURE"
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = 512
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
size = max(W, H)
cam.location = (size * 0.62, -size * 1.35, H * 0.72)
direction = (np.array([0, 0, H * 0.5]) - np.array(cam.location))
cam.rotation_euler = (math.atan2(math.hypot(direction[0], direction[1]), -direction[2]), 0,
                      math.atan2(direction[1], direction[0]) - math.pi / 2)
cam.data.lens = 45
scene.render.filepath = str(D / "thumb.png")
bpy.ops.render.render(write_still=True)
print("cc-piano relief done:", D, len(obj.data.vertices), "verts")
