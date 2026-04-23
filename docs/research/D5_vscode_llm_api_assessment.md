# D5: VSCode LLM API 可用性评估报告

> 调研基准日期：2026-04-18  
> 信息来源：VSCode 官方文档、VSCode API 参考、官方博客、GitHub Issue 追踪  
> API 稳定性等级：Stable（v1.104+），但仍在快速演进中

---

## 一、核心 API 概览

### 1.1 两大 API 体系

VSCode 提供两套与语言模型相关的 API：

| API | 定位 | 稳定性 | 适用场景 |
|-----|------|--------|----------|
| **Language Model Chat Provider API** | 供"模型提供商"注册自定义模型 | Stable (v1.104+) | BYOK 扩展开发 |
| **Language Model Access API** (`vscode.lm`) | 供"扩展开发者"调用模型 | Stable (v1.100+) | 普通扩展使用 LLM |

---

## 二、Language Model Chat Provider API 详解

### 2.1 接口完整定义

```typescript
// 核心接口：LanguageModelChatProvider
interface LanguageModelChatProvider<T extends LanguageModelChatInformation = LanguageModelChatInformation> {
    // 模型信息变化事件
    readonly onDidChangeLanguageModelChatInformation?: Event<void>;
    
    // 返回可用模型列表
    provideLanguageModelChatInformation(
        options: { silent: boolean },
        token: CancellationToken
    ): ProviderResult<T[]>;
    
    // 处理聊天请求（核心方法）
    provideLanguageModelChatResponse(
        model: T,
        messages: readonly LanguageModelChatRequestMessage[],
        options: ProvideLanguageModelChatResponseOptions,
        progress: Progress<LanguageModelResponsePart>,
        token: CancellationToken
    ): Thenable<void>;
    
    // Token 计数
    provideTokenCount(
        model: T,
        text: string | LanguageModelChatRequestMessage,
        token: CancellationToken
    ): Thenable<number>;
}
```

### 2.2 数据结构

```typescript
// 模型信息
interface LanguageModelChatInformation {
    readonly id: string;           // 模型唯一标识
    readonly name: string;         // 显示名称
    readonly family: string;       // 模型族（如 'gpt4', 'llama'）
    readonly version: string;      // 版本号
    readonly maxInputTokens: number;
    readonly maxOutputTokens: number;
    readonly capabilities: {
        readonly imageInput?: boolean;
        readonly toolCalling?: boolean | number;  // true 或最大工具数
    };
}

// 请求消息
interface LanguageModelChatRequestMessage {
    readonly role: LanguageModelChatMessageRole;  // User=1, Assistant=2
    readonly name: string | undefined;
    readonly content: readonly (LanguageModelTextPart | LanguageModelToolResultPart | LanguageModelToolCallPart | unknown)[];
}

// 响应部分（流式）
type LanguageModelResponsePart = 
    | LanguageModelTextPart           // 文本内容
    | LanguageModelToolCallPart       // 工具调用请求
    | LanguageModelToolResultPart;    // 工具执行结果
```

### 2.3 最小可行实现示例

```typescript
// src/extension.ts — 自定义 LLM Provider 扩展
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    const provider: vscode.LanguageModelChatProvider = {
        async provideLanguageModelChatInformation(options, token) {
            if (options.silent) {
                // 静默模式下不弹窗，直接返回已配置的模型
                return getConfiguredModels();
            }
            // 非静默模式：引导用户配置 API Key
            await promptForApiKey();
            return getConfiguredModels();
        },
        
        async provideLanguageModelChatResponse(model, messages, options, progress, token) {
            // 转换消息格式为 OpenAI/DeepSeek 格式
            const apiMessages = messages.map(m => ({
                role: m.role === vscode.LanguageModelChatMessageRole.User ? 'user' : 'assistant',
                content: m.content
                    .filter(p => p instanceof vscode.LanguageModelTextPart)
                    .map(p => p.value)
                    .join('')
            }));
            
            // 调用自定义 API
            const response = await callCustomLLM(model.id, apiMessages, {
                tools: options.tools,
                toolMode: options.toolMode
            });
            
            // 流式返回结果
            for await (const chunk of response.stream) {
                if (token.isCancellationRequested) break;
                progress.report(new vscode.LanguageModelTextPart(chunk.content));
            }
        },
        
        async provideTokenCount(model, text) {
            return Math.ceil(text.toString().length / 4);
        }
    };
    
    // 注册 Provider
    const disposable = vscode.lm.registerChatModelProvider('my-provider', provider, {
        name: 'My Custom LLM',
        version: '1.0.0'
    });
    
    context.subscriptions.push(disposable);
}
```

---

## 三、Language Model Access API 详解

### 3.1 扩展开发者如何调用模型

```typescript
// 1. 选择模型
const models = await vscode.lm.selectChatModels({
    vendor: 'copilot',      // 或 'my-provider'（自定义）
    family: 'gpt-4o'
});
const model = models[0];

// 2. 发送请求
const messages = [
    vscode.LanguageModelChatMessage.User('解释这段代码')
];

const response = await model.sendRequest(
    messages,
    { toolMode: vscode.LanguageModelChatToolMode.Auto },
    new vscode.CancellationTokenSource().token
);

// 3. 读取流式响应
for await (const fragment of response.text) {
    console.log(fragment);
}
```

### 3.2 工具调用支持

```typescript
// 注册自定义工具
const myTool: vscode.LanguageModelTool<object> = {
    async invoke(options, token) {
        const result = await doSomething(options.input);
        return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(result)
        ]);
    }
};

vscode.lm.tools.registerTool('my-tool', myTool);

// 在请求中传递工具
const response = await model.sendRequest(
    messages,
    { tools: [myTool] },
    token
);

// 处理工具调用请求
for await (const part of response.stream) {
    if (part instanceof vscode.LanguageModelToolCallPart) {
        const toolResult = await vscode.lm.invokeTool(part.name, part.input, token);
        // 将结果传回模型...
    }
}
```

---

## 四、BYOK（Bring Your Own Key）实现方案

### 4.1 用户配置流程

```
用户安装扩展 → 打开 Chat: Manage Language Models
    │
    ├── 选择"Add Models"
    │
    ├── 选择 Provider 类型：
    │   ├── 内置提供商（OpenRouter / Ollama / Google / OpenAI）
    │   └── 自定义扩展提供商（本竞品）
    │
    └── 输入 API Key / Endpoint URL → 测试连接 → 保存
```

### 4.2 实现 BYOK 的关键代码

```typescript
// 配置存储
const API_KEY_SECRET = 'myProvider.apiKey';
const ENDPOINT_CONFIG = 'myProvider.endpoint';

async function promptForApiKey(): Promise<string | undefined> {
    const apiKey = await vscode.window.showInputBox({
        prompt: 'Enter your API Key',
        password: true,
        ignoreFocusOut: true
    });
    if (apiKey) {
        await vscode.secrets.store(API_KEY_SECRET, apiKey);
    }
    return apiKey;
}

async function getApiKey(): Promise<string | undefined> {
    return vscode.secrets.get(API_KEY_SECRET);
}
```

### 4.3 当前限制（重要）

| 限制 | 说明 | 缓解策略 |
|------|------|----------|
| **需要 Copilot 计划** | 即使使用本地/BYOK 模型，仍需 GitHub Copilot Free 或更高计划 | 这是微软的商业限制，无法绕过 |
| **必须在线** | 使用本地模型仍需连接 Copilot 服务进行认证 | 等待微软解除此限制 |
| **Enterprise/Business 不支持 BYOK** | 企业版暂不可用，计划 2026 下半年支持 | MVP 阶段聚焦个人开发者 |
| **对话 Session 不可见** | `ProvideLanguageModelChatResponseOptions` 不含 `sessionResource`（GitHub Issue #305853） | 使用消息历史中的嵌入式标记作为 workaround |

---

## 五、获取 VSCode 工作区上下文

### 5.1 可用 API 清单

```typescript
// 项目结构
const workspaceFolders = vscode.workspace.workspaceFolders;
const files = await vscode.workspace.findFiles('**/*.py', '**/node_modules/**');

// Git 状态
const gitExtension = vscode.extensions.getExtension('vscode.git')?.exports;
const repo = gitExtension.getAPI(1).repositories[0];
const diff = await repo.diffWithHEAD();

// 活动文件
const activeEditor = vscode.window.activeTextEditor;
const currentFile = activeEditor?.document.uri;
const cursorPosition = activeEditor?.selection.active;
const selectedText = activeEditor?.document.getText(activeEditor.selection);

// 符号与诊断
const symbols = await vscode.commands.executeCommand(
    'vscode.executeDocumentSymbolProvider',
    currentFile
);
const diagnostics = vscode.languages.getDiagnostics(currentFile);
```

### 5.2 上下文组装策略

```typescript
async function buildWorkspaceContext(): Promise<string> {
    const parts = [];
    
    // 1. 项目结构摘要（前 20 个文件）
    const files = await vscode.workspace.findFiles('*', '**/node_modules/**', 20);
    parts.push(`Project files: ${files.map(f => f.path).join(', ')}`);
    
    // 2. Git 状态
    const repo = getGitRepo();
    if (repo) {
        parts.push(`Git branch: ${repo.state.HEAD?.name}`);
        parts.push(`Changed files: ${repo.state.workingTreeChanges.map(c => c.uri.path).join(', ')}`);
    }
    
    // 3. 活动文件上下文
    const editor = vscode.window.activeTextEditor;
    if (editor) {
        parts.push(`Current file: ${editor.document.fileName}`);
        parts.push(`Cursor at line ${editor.selection.active.line + 1}`);
        parts.push(`Selected: ${editor.document.getText(editor.selection) || '(none)'}`);
    }
    
    return parts.join('\n');
}
```

---

## 六、Python 扩展 API（@vscode/python-extension）

### 6.1 可用性评估

| 特性 | 状态 | 说明 |
|------|------|------|
| Python 解释器发现 | ✅ Stable | `python.environments.getActiveEnvironment()` |
| 包管理器检测 | ✅ Stable | 自动检测 pip/conda/poetry/uv |
| LSP 客户端访问 | ⚠️ Limited | 可通过 `vscode.languages` 间接访问 |
| 测试发现 | ✅ Stable | `python.testing` API |
| 调试器控制 | ⚠️ Proposed | 需使用 Debug Adapter Protocol |

### 6.2 Python 环境信息获取

```typescript
const pythonExtension = vscode.extensions.getExtension('ms-python.python');
if (pythonExtension) {
    const pythonApi = pythonExtension.exports;
    const env = await pythonApi.environments.resolveEnvironment(
        pythonApi.environments.getActiveEnvironmentPath()
    );
    console.log('Python:', env.executable.uri?.fsPath);
    console.log('Version:', env.version);
}
```

---

## 七、已知限制与风险

| 限制/风险 | 严重程度 | 影响 | 缓解策略 |
|-----------|----------|------|----------|
| 需要 Copilot 计划 | 🔴 高 | 所有用户必须注册 Copilot | MVP 聚焦 Copilot Free 用户；长期推动微软解除限制 |
| Session 不可见 | 🟡 中 | 无法维持 Provider 侧的对话状态 | 消息历史嵌入标记 workaround |
| API 仍在演进 | 🟡 中 | 未来版本可能 Breaking Change | 防御式编程，关注 VSCode 更新日志 |
| 企业版不支持 BYOK | 🟡 中 | 企业用户无法使用 | 明确 MVP 边界，企业版后续支持 |
| 工具调用无完整 MCP 传递 | 🟡 中 | MCP 工具定义需转换 | 编写 MCP ↔ VSCode Tool 适配层 |
| Rate Limiting | 🟢 低 | 扩展需负责任地使用 | 实现请求队列和退避策略 |

---

## 八、技术可行性结论

| 评估项 | 结论 |
|--------|------|
| **VSCode LLM API 成熟度** | ✅ 可用，但存在商业限制（Copilot 依赖） |
| **BYOK 实现复杂度** | 🟡 中等，Provider API 设计良好 |
| **工作区上下文获取** | ✅ 丰富，可获取文件/GIT/光标/诊断信息 |
| **Python 环境集成** | ✅ 稳定，ms-python 扩展提供完整 API |
| **与 MCP 协议集成** | 🟡 需适配层，但技术上可行 |
| **整体可行性** | ✅ **可行**，但需接受 Copilot 计划依赖作为当前约束 |

---

## 九、信息来源

- [VSCode Language Model Chat Provider API Guide](https://code.visualstudio.com/api/extension-guides/ai/language-model-chat-provider)
- [VSCode Language Model API Guide](https://code.visualstudio.com/api/extension-guides/ai/language-model)
- [VSCode API Reference](https://code.visualstudio.com/api/references/vscode-api)
- [Bring Your Own Key Blog Post](https://code.visualstudio.com/blogs/2025/10/22/bring-your-own-key)
- [GitHub Issue #305853 — Session Resource Missing](https://github.com/microsoft/vscode/issues/305853)
- [Python Extension API](https://code.visualstudio.com/api/python/python-api)
