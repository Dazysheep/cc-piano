"""各平台上传页的配置。

页面元素按「多个候选选择器、找到哪个用哪个」的方式定位；平台改版后只需要在这里补选择器。
"""
from dataclasses import dataclass, field


@dataclass
class Platform:
    key: str
    name: str
    url: str
    vertical: bool                 # 发竖屏版
    title_max: int | None          # None = 没有单独的标题框
    title_min: int = 0
    desc_max: int = 1000
    tag_mode: str = "inline"       # inline = 在正文里输入 #话题；input = 单独的标签输入框
    tag_confirm: str = "Space"     # 输入 #话题 后按的键
    tag_max: int = 5
    title_sel: list[str] = field(default_factory=list)
    desc_sel: list[str] = field(default_factory=list)
    tag_sel: list[str] = field(default_factory=list)
    done_text: list[str] = field(default_factory=list)   # 出现这些字说明视频已上传完
    note: str = ""                 # 需要你手动确认的事项
    # 「自主声明」下拉：先点开（按显示文字找），再选 AI 生成那一项
    declare_open: list[str] = field(default_factory=list)
    declare_ai: list[str] = field(default_factory=list)


PLATFORMS = {
    "douyin": Platform(
        key="douyin", name="抖音", vertical=True,
        url="https://creator.douyin.com/creator-micro/content/upload",
        title_max=30, desc_max=1000, tag_confirm="Space",
        title_sel=['input[placeholder*="作品标题"]', 'input[placeholder*="标题"]'],
        desc_sel=['.zone-container[contenteditable="true"]', 'div[data-placeholder*="简介"][contenteditable="true"]',
                  '.editor-kit-container [contenteditable="true"]', 'div[contenteditable="true"]'],
        done_text=["重新上传", "更换视频", "上传成功"],
        note="封面请在页面里选择 cover_vertical.jpg",
        declare_open=["请选择自主声明", "自主声明"],
        declare_ai=["内容由AI生成", "内容由 AI 生成", "AI生成"],
    ),
    "xiaohongshu": Platform(
        key="xiaohongshu", name="小红书", vertical=True,
        url="https://creator.xiaohongshu.com/publish/publish?source=official",
        title_max=20, desc_max=1000, tag_confirm="Enter",
        title_sel=['input[placeholder*="标题"]', 'input.d-text'],
        desc_sel=['div.ql-editor', '#post-textarea', 'div[contenteditable="true"]'],
        done_text=["上传成功", "重新上传", "替换视频"],
        note="封面请在页面里选择 cover_vertical.jpg",
    ),
    "bilibili": Platform(
        key="bilibili", name="B 站", vertical=False,
        url="https://member.bilibili.com/platform/upload/video/frame",
        title_max=80, desc_max=2000, tag_mode="input", tag_max=10,
        title_sel=['input[placeholder*="标题"]', '.video-title input'],
        desc_sel=['.ql-editor', 'div[contenteditable="true"]', 'textarea[placeholder*="简介"]'],
        tag_sel=['input[placeholder*="回车"]', 'input[placeholder*="标签"]', '.tag-input-wrp input'],
        done_text=["上传完成", "重新上传"],
        note="请确认分区（建议「音乐 · 演奏」）和类型（自制）",
    ),
    "kuaishou": Platform(
        key="kuaishou", name="快手", vertical=True,
        url="https://cp.kuaishou.com/article/publish/video",
        title_max=None, desc_max=500, tag_confirm="Space",
        desc_sel=['#work-description-edit', 'div[placeholder*="描述"][contenteditable="true"]',
                  'div[contenteditable="true"]'],
        done_text=["上传成功", "重新上传", "预览作品"],
        note="封面请在页面里选择 cover_vertical.jpg",
    ),
    "channels": Platform(
        key="channels", name="视频号", vertical=True,
        url="https://channels.weixin.qq.com/platform/post/create",
        title_max=16, title_min=6, desc_max=1000, tag_confirm="Space",
        title_sel=['input[placeholder*="短标题"]', 'input[placeholder*="概括"]'],
        desc_sel=['.input-editor[contenteditable]', 'div[data-placeholder*="描述"]', 'div[contenteditable="true"]'],
        done_text=["删除", "更换", "上传完成"],
        note="短标题需 6-16 字；封面请在页面里确认",
    ),
}
