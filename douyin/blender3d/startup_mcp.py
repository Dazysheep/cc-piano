"""带界面的 Blender 启动时运行（blender.py open_gui）：启用项目里的 blender-mcp 插件，并自动开启 MCP 连接，
Claude Code 里登记的 blender MCP 服务（D:\\cc-engine\\.mcp.json）就能连上来操作这个 Blender。"""
import addon_utils
import bpy

NAME = "blender_mcp_addon"


def start():
    try:
        if not bpy.context.scene.blendermcp_server_running:
            bpy.ops.blendermcp.start_server()
        print("cc-piano: MCP for Blender 已连接，端口", bpy.context.scene.blendermcp_port)
    except Exception as e:          # 插件没加载上：在 Blender 里也能手动点「Connect to Claude」
        print("cc-piano: 没能自动开启 MCP 连接：", e)
    return None


addon_utils.enable(NAME, default_set=True, persistent=True)
bpy.app.timers.register(start, first_interval=1.5)
