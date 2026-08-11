# DeepSeek 对话导出查看器

一个用于浏览和导出 DeepSeek 官方导出的 `conversations.json` 对话文件的桌面工具（Python + Tkinter）。

## 功能

- **懒加载解析**：启动时只建立轻量索引（标题、ID、时间、字节偏移），选中的对话才按需切片解析，内存占用低，适合大文件。
- **标题浏览与搜索**：按时间列出全部对话标题，支持关键字实时筛选。
- **对话预览**：点击标题即在右侧显示该对话全部消息，区分用户 / 助手，可显示 R1 模型的思考过程。
- **导出 Markdown**：将选中对话导出为 Markdown 文件，支持导出全部或指定条数范围（如 `3-20`），可选择是否包含思考过程。

## 环境要求

- Python 3.8+（含 tkinter，官方 Windows 安装包默认自带）

## 使用方式

```bash
python deepseek_viewer.py
```

启动后：

1. 工具会自动加载 `B:\杂物\deepseek_data-2026-08-11\conversations.json`；或点击「打开」手动选择导出文件，点击「重新加载」可再次解析。
2. 左侧列表点击标题即可查看对话内容。
3. 底部按钮导出 Markdown：
   - **导出 Markdown(全部)**：导出当前对话全部内容。
   - **导出部分…**：输入条数范围（如 `3-20`），或输入 `all` 导出全部。
4. 勾选「导出/显示思考过程」可包含 deepseek-reasoner 的思维链（折叠在 `<details>` 中）。

## 导出文件格式示例

```markdown
# 你和最新ChatGPT有什么区别，对比之下谁更强大

> 模型: deepseek-reasoner | 创建: 2025-01-28 00:59:07 | 更新: 2025-01-28 01:01:29

---
## 用户 · 第1条 · 2025-01-28 00:59:08 · deepseek-reasoner

你和最新ChatGPT有什么区别，对比之下谁更强大

---
## 助手 · 第2条 · 2025-01-28 00:59:08 · deepseek-reasoner

<回答内容>

<details><summary>思考过程</summary>

<思维链内容>

</details>
```

## 关于 conversations.json 格式

该文件是 UTF-8 编码的单行 JSON 数组，每个元素为一段对话：

```json
{
  "id": "UUID",
  "title": "对话标题",
  "inserted_at": "2025-01-27T13:39:24.513000+08:00",
  "updated_at": "2025-01-27T13:47:48.485000+08:00",
  "mapping": {
    "root": { "id": "root", "parent": null, "children": ["1"], "message": null },
    "1": { "id": "1", "parent": "root", "children": ["2"],
           "message": {
             "model": "deepseek-chat",
             "inserted_at": "...",
             "fragments": [
               { "type": "REQUEST", "content": "用户问题" },
               { "type": "RESPONSE", "content": "助手回答" },
               { "type": "THINK", "content": "思考过程" }
             ]
           } }
  }
}
```

- `mapping` 是一棵消息树，`root` 为根节点，各节点通过 `parent` / `children` 串联。
- `fragments` 中的 `type` 取值：`REQUEST`（用户）、`RESPONSE`（助手）、`THINK`（reasoner 模型的推理过程）。

## 实现说明

- 索引阶段使用标准库 `json.JSONDecoder.raw_decode` 逐条切分顶层对话对象，只保留轻量字段，避免一次性完整解析大文件。
- 查看 / 导出时按字节偏移切片，仅解析当前选中的对话。
- 索引在后台线程构建，界面不卡顿，带进度条提示。
