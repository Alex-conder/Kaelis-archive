"""
为 en-US.json 生成基础英文翻译。
B-2: 多语言国际化基础设施
"""

import json
from pathlib import Path


def translate(text: str) -> str:
    """简单规则映射中文到英文。"""
    # 常见模式替换
    mappings = {
        "退出登录": "Sign Out",
        "成就解锁": "Achievement Unlocked!",
        "审批": "Approval",
        "待审批请求": "Pending Approvals",
        "搜索记忆、技能、页面...": "Search memories, skills, pages...",
        "未找到匹配结果": "No matching results",
        "出错了": "Something went wrong",
        "策略解释": "Strategy Explanation",
        "记忆统计": "Memory Statistics",
        "开始对话后，这里会展示你的记忆增长": "Start chatting to see your memory growth",
        "各层记忆占比": "Memory Layer Distribution",
        "月度增长趋势": "Monthly Growth Trend",
        "创建 Agent 向导即将上线": "Agent creation wizard coming soon",
        "搜索 Agent...": "Search Agent...",
        "暂无 Agent": "No Agents yet",
        "创建您的第一个 Agent 开始工作": "Create your first Agent to get started",
        "我是 Kaelis，你的 AI 第二大脑": "I'm Kaelis, your AI second brain",
        "Agent 正在思考...": "Agent is thinking...",
        "分析代码": "Analyze Code",
        "记录偏好": "Record Preferences",
        "查询知识": "Query Knowledge",
        "安全健康度": "Security Health",
        "Kaelis 今日推荐": "Kaelis Today's Pick",
        "欢迎回来！": "Welcome back!",
        "今日简报": "Daily Brief",
        "安全态势": "Security Posture",
        "基于你的工作，推荐以下记忆": "Recommended memories based on your work",
        "暂无推荐，多和 Kaelis 聊聊吧": "No recommendations yet. Chat more with Kaelis!",
        "成长与摘要": "Growth & Summary",
        "已复制到剪贴板！": "Copied to clipboard!",
        "复制失败，请手动分享": "Copy failed. Please share manually",
        "生成图片失败": "Image generation failed",
        "我的成长": "My Growth",
        "你与 Kaelis 的共同进化之路": "Your co-evolution journey with Kaelis",
        "综合成长指数": "Composite Growth Index",
        "成就墙": "Achievement Wall",
        "输入用户名": "Enter username",
        "暂无记忆记录": "No memory records yet",
        "列表视图": "List View",
        "时间线视图": "Timeline View",
        "你的第二大脑还是一片空白": "Your second brain is still empty",
        "和 Kaelis 聊聊天，这里就会开始积累记忆": "Chat with Kaelis to start building memories",
        "你可能需要：": "You might need:",
        "我的 AI 记住了这个": "My AI remembered this",
        "作者": "Author",
        "创建时间": "Created",
        "更新时间": "Updated",
        "空间名称": "Space Name",
        "描述（可选）": "Description (optional)",
        "还没有共享空间": "No shared spaces yet",
        "创建一个来开始协作": "Create one to start collaborating",
        "订阅管理": "Subscription Management",
        "标签，如: project,goal": "Tags, e.g. project,goal",
        "查询模式（可选）": "Query pattern (optional)",
        "暂无订阅": "No subscriptions",
        "查看历史": "View History",
        "取消订阅": "Unsubscribe",
        "实时事件流": "Real-time Event Stream",
        "暂无投递事件": "No delivery events",
        "最近投递": "Recent Deliveries",
        "检测到记忆冲突": "Memory conflicts detected",
        "搜索共享记忆...": "Search shared memories...",
        "这个空间还没有记忆": "No memories in this space yet",
        "使用 MCP memory_remember 工具或 API 写入": "Use MCP memory_remember tool or API to write",
        "选择一个共享空间查看记忆": "Select a shared space to view memories",
        "安全中心": "Security Center",
        "实时监控 Kaelis 安全态势": "Real-time Kaelis security monitoring",
        "安全评分": "Security Score",
        "五大安全维度": "Five Security Dimensions",
        "暂无已注册 Agent": "No registered Agents",
        "资源": "Resources",
        "操作": "Operations",
        "最小角色": "Min Role",
        "暂无审计日志": "No audit logs",
        "策略能耗概览": "Policy Energy Overview",
        "策略": "Policy",
        "描述": "Description",
        "能耗": "Energy",
        "节能模式：": "Energy Saving Mode:",
        "外观主题": "Appearance Theme",
        "声音反馈": "Sound Feedback",
        "启用消息音效": "Enable message sounds",
        "键盘快捷键": "Keyboard Shortcuts",
        "快捷键自定义功能即将上线": "Custom shortcuts coming soon",
        "搜索技能...": "Search skills...",
        "按成功率": "By Success Rate",
        "按使用频率": "By Usage Frequency",
        "按最近使用": "By Recently Used",
        "按趋势": "By Trend",
        "加载能力库...": "Loading capabilities...",
        "技能库还是空的": "Skill library is empty",
        "从 agentskills.io 发现技能，或让 Kaelis 在对话中自动学习": "Discover skills from agentskills.io, or let Kaelis learn automatically",
        "从社区导入功能即将上线": "Community import coming soon",
        "准备就绪！": "Ready!",
        "正在进入 Kaelis 工作台...": "Entering Kaelis Workbench...",
        "欢迎来到 Kaelis": "Welcome to Kaelis",
        "您的 AI 科研工作台，3 步即可开始知识提取": "Your AI research workbench. Start knowledge extraction in 3 steps",
        "配置 LLM API Key": "Configure LLM API Key",
        "导入示例工作流": "Import Sample Workflow",
        "开始 KG 提取": "Start KG Extraction",
        "配置 LLM": "Configure LLM",
        "选择提供商并输入 API Key，我们将测试连接": "Select provider and enter API Key. We'll test the connection",
        "提供商": "Provider",
        "连接测试成功": "Connection test successful",
        "连接失败，请检查 API Key": "Connection failed. Please check API Key",
        "导入首个工作流": "Import First Workflow",
        "从模板开始，快速体验 KG 提取": "Start from template for quick KG extraction",
        "文献综述模板": "Literature Review Template",
        "自动提取论文中的实体、关系与核心观点，生成知识图谱": "Auto-extract entities, relations and key points from papers",
        "KG 提取": "KG Extraction",
        "快速上手": "Quick Start",
        "掌握这 3 个核心功能，让 Kaelis 更好地为你服务": "Master these 3 features to get the most from Kaelis",
        "对话中搜索记忆": "Search memories in chat",
        "输入": "Type",
        "即可搜索历史记忆": "to search historical memories",
        "发现技能": "Discover Skills",
        "进入「Capabilities」页面，浏览和安装扩展技能": "Go to Capabilities to browse and install skills",
        "安全体检": "Security Check",
        "进入「Security」页面，运行一次安全审计确保": "Go to Security to run an audit",
    }

    if text in mappings:
        return mappings[text]

    # 默认策略：返回原文（后续迭代人工翻译）
    return text


def main():
    project_root = Path(__file__).parent.parent
    locales_dir = project_root / "web/frontend/src/i18n/locales"

    with open(locales_dir / "zh-CN.json", "r", encoding="utf-8") as f:
        zh_cn = json.load(f)

    en_us = {k: translate(v) for k, v in zh_cn.items()}

    with open(locales_dir / "en-US.json", "w", encoding="utf-8") as f:
        json.dump(en_us, f, ensure_ascii=False, indent=2)

    translated = sum(1 for v in en_us.values() if v != list(en_us.keys())[list(en_us.values()).index(v)])
    print(f"Translated {translated}/{len(en_us)} keys to English")
    print(f"Saved to {locales_dir}/en-US.json")


if __name__ == "__main__":
    main()
