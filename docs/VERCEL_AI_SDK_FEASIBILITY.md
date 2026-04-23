# Vercel AI SDK 集成可行性评估

## 现状分析

### 当前后端 SSE 协议（自定义）

端点：`POST /api/kg-flywheel/chat/stream`

```
data: {"type": "content", "content": "第一段落..."}

data: {"type": "content", "content": "第二段落..."}

data: {"type": "done", "session_id": "abc", "state": "COMPLETED", "data": {"strategy": {...}}, "tool_calls": []}

data: [DONE]
```

特点：
- 自定义 `type` 字段区分内容块和结束元数据
- 结束消息携带 `strategy`、`new_user_info` 等 Kaelis 专属字段
- 非 OpenAI 兼容格式

### Vercel AI SDK useChat 期望

`useChat` 默认需要后端返回符合 **Vercel AI SDK Provider Protocol** 的流：

```
data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":"..."}}]}

data: [DONE]
```

或简化的 `StreamPart` 格式：

```
data: {"type":"text","value":"..."}

data: {"type":"finish_message","finishReason":"stop","usage":{"promptTokens":10,"completionTokens":20}}
```

## 适配方案

### 方案 A：前端自定义 fetch（推荐评估）

在 `useChat` 中传入自定义 `fetch` 函数，将后端 SSE 转换为 AI SDK `StreamPart`：

```tsx
import { useChat } from '@ai-sdk/react'

function ChatPage() {
  const { messages, input, handleSubmit } = useChat({
    api: '/api/kg-flywheel/chat/stream',
    fetch: async (url, options) => {
      const res = await fetch(url, options)
      // 将自定义 SSE 转换为 ReadableStream<StreamPart>
      const transformed = res.body!.pipeThrough(new TransformStream({
        transform(chunk, controller) {
          // 解析 {type: "content", content: "..."} → {type: "text", value: "..."}
          // 解析 {type: "done", ...} → {type: "finish_message", ...}
        }
      }))
      return new Response(transformed)
    }
  })
}
```

**优点**：
- 不修改后端
- 可以平滑渐进引入

**缺点**：
- `useChat` 的消息格式（`Message`）与当前 Kaelis `Message` 接口不完全兼容
- Kaelis 专属字段（`strategy`、`new_user_info`）需要额外处理，可能丢失
- 需要重写 ChatPage 的消息渲染逻辑
- 流式更新粒度可能不同（AI SDK 按 token，Kaelis 按段落）

### 方案 B：后端新增兼容端点

新增 `/api/kg-flywheel/chat/stream/ai-sdk`，返回 Vercel AI SDK 兼容格式：

```python
@app.route('/api/kg-flywheel/chat/stream/ai-sdk', methods=['POST'])
def chat_stream_ai_sdk():
    # 复用现有逻辑，但输出格式转换为 StreamPart
    for chunk in existing_stream():
        yield f'data: {json.dumps({"type":"text","value":chunk["content"]})}\n\n'
    yield f'data: {json.dumps({"type":"finish_message","finishReason":"stop"})}\n\n'
```

**优点**：
- 前端无需复杂转换
- 可为其他 AI SDK 客户端服务

**缺点**：
- Kaelis 专属字段（strategy 等）需要以 `annotations` 或自定义 extension 传递
- 需要后端开发工作量
- 维护两个 SSE 端点增加复杂度

### 方案 C：保持现状（推荐当前阶段）

继续使用原生 SSE + TanStack Query `useMutation`：

```tsx
const mutation = useMutation({
  mutationFn: async (content: string) => {
    await chatApi.sendMessageStream({ message: content }, (chunk) => {
      // 直接处理自定义 chunk 格式
    })
  }
})
```

**优点**：
- 完全控制消息格式和状态管理
- Kaelis 专属字段（strategy、new_user_info）自然传递
- 与现有 chatStore 架构无缝集成
- 无额外依赖

**缺点**：
- 需要手动处理流式状态（已有实现）
- 无法利用 AI SDK 的生态（如自动重试、工具调用抽象等）

## 结论

| 维度 | 方案 A | 方案 B | 方案 C（现状） |
|------|--------|--------|---------------|
| 后端改动 | 无 | 中 | 无 |
| 前端改动 | 大 | 中 | 无 |
| Kaelis 字段兼容性 | 差 | 中 | 优 |
| 长期维护成本 | 高 | 中 | 低 |
| 生态收益 | 中 | 中 | 无 |

**建议：当前阶段采用方案 C，延后评估 AI SDK 集成。**

理由：
1. 当前 SSE 逻辑稳定，已实现流式输出、策略标签、用户信息提取等完整功能
2. 引入 AI SDK 需要重构消息格式和状态管理，ROI 不高
3. 若未来需要 AI SDK 的工具调用抽象、自动重试等功能，再考虑方案 B（后端兼容端点）
4. 建议观察 AI SDK 后续版本对自定义 provider 的支持，可能降低集成成本

## 后续行动

- [ ] 关注 `@ai-sdk/provider` 规范演进
- [ ] 若后端需要服务多客户端，评估新增 `/chat/stream/ai-sdk` 端点
- [ ] 当前保持 `chatApi.sendMessageStream` 原生实现
