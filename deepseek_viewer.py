import json
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

DEFAULT_FILE = r"B:\杂物\deepseek_data-2026-08-11\conversations.json"


def build_index(text):
    decoder = json.JSONDecoder()
    n = len(text)
    idx = 0
    while idx < n and text[idx] in " \t\r\n":
        idx += 1
    if idx < n and text[idx] == "[":
        idx += 1
    index = []
    while True:
        while idx < n and text[idx] in " \t\r\n,":
            idx += 1
        if idx >= n or text[idx] == "]":
            break
        start = idx
        obj, end = decoder.raw_decode(text, idx)
        index.append(
            {
                "id": obj.get("id"),
                "title": obj.get("title"),
                "inserted_at": obj.get("inserted_at"),
                "updated_at": obj.get("updated_at"),
                "start": start,
                "end": end,
            }
        )
        idx = end
    return index


def load_conversation(text, entry):
    chunk = text[entry["start"]:entry["end"]]
    return json.loads(chunk)


def fmt_ts(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(iso)


def ordered_messages(mapping):
    root = mapping.get("root")
    if not root:
        return []
    out = []

    def walk(node_id):
        node = mapping.get(node_id)
        if node is None:
            return
        if node.get("message"):
            out.append(node["message"])
        for c in node.get("children") or []:
            walk(c)

    walk("root")
    return out


def split_fragments(msg):
    parts = []
    think = []
    for f in msg.get("fragments", []):
        content = (f.get("content") or "").strip()
        if not content:
            continue
        if f.get("type") == "THINK":
            think.append(content)
        else:
            parts.append(content)
    return parts, think


def to_markdown(meta, messages, include_think, start=1, end=None):
    if end is None:
        end = len(messages)
    lines = ["# " + (meta.get("title") or ""), ""]
    model = messages[0].get("model") if messages else ""
    lines.append(
        f"> 模型: {model} | 创建: {fmt_ts(meta.get('inserted_at'))} | 更新: {fmt_ts(meta.get('updated_at'))}"
    )
    lines.append("")
    for i, msg in enumerate(messages, 1):
        if i < start or i > end:
            continue
        parts, think = split_fragments(msg)
        if not parts and not think:
            continue
        is_user = any(f.get("type") == "REQUEST" for f in msg.get("fragments", []))
        role = "用户" if is_user else "助手"
        lines.append("---")
        lines.append(
            f"## {role} · 第{i}条 · {fmt_ts(msg.get('inserted_at'))} · {msg.get('model') or ''}"
        )
        lines.append("")
        if parts:
            lines.append("\n\n".join(parts))
        if include_think and think:
            lines.append("")
            lines.append("<details><summary>思考过程</summary>")
            lines.append("")
            lines.append("\n\n".join(think))
            lines.append("")
            lines.append("</details>")
        lines.append("")
    return "\n".join(lines)


class App:
    def __init__(self, root):
        self.root = root
        self.text = None
        self.index = []
        self.filtered = []
        self.current_path = ""
        root.title("DeepSeek 对话导出查看器")
        root.geometry("1000x640")
        self._build_ui()
        if DEFAULT_FILE:
            self.path_var.set(DEFAULT_FILE)
            self.start_load(DEFAULT_FILE)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        top.pack(fill=tk.X)
        ttk.Label(top, text="文件:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.path_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(top, text="打开", command=self.ask_open).pack(side=tk.LEFT)
        ttk.Button(top, text="重新加载", command=self.reload).pack(side=tk.LEFT, padx=(4, 0))

        bar = ttk.Frame(self.root, padding=(8, 2, 8, 2))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="搜索标题:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search = ttk.Entry(bar, textvariable=self.search_var)
        search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        search.bind("<KeyRelease>", lambda e: self.apply_filter())
        self.think_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bar, text="导出/显示思考过程", variable=self.think_var
        ).pack(side=tk.LEFT, padx=(6, 0))
        self.newest_first = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bar, text="最新在上", variable=self.newest_first,
            command=self.apply_filter,
        ).pack(side=tk.LEFT, padx=(6, 0))

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        self.listbox = tk.Listbox(left, font=("Microsoft YaHei UI", 10))
        sb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        self.view = tk.Text(
            right,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),
            state=tk.DISABLED,
        )
        vsb = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.view.yview)
        hsb = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.view.xview)
        self.view.configure(
            yscrollcommand=vsb.set, xscrollcommand=hsb.set
        )
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        paned.add(right, weight=3)

        self.view.tag_configure("user", foreground="#1a66c4")
        self.view.tag_configure("assistant", foreground="#0f7b3a")
        self.view.tag_configure("think", foreground="#888888")
        self.view.tag_configure("meta", foreground="#666666")

        bottom = ttk.Frame(self.root, padding=(8, 4, 8, 8))
        bottom.pack(fill=tk.X)
        ttk.Button(bottom, text="导出 Markdown(全部)", command=self.export_all).pack(
            side=tk.LEFT
        )
        ttk.Button(bottom, text="导出部分…", command=self.export_range).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(
            bottom, mode="indeterminate", length=140
        )
        self.progress.pack(side=tk.RIGHT, padx=8)

    def set_status(self, msg):
        self.status_var.set(msg)

    def start_load(self, path):
        self.progress.start(12)
        self.set_status(f"正在解析 {path} ...")

        def worker():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                index = build_index(text)
                self.root.after(
                    0, lambda: self._on_loaded(text, index, path)
                )
            except Exception as e:
                self.root.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_loaded(self, text, index, path):
        self.progress.stop()
        self.text = text
        self.index = index
        self.current_path = path
        self.apply_filter()
        self.set_status(f"已加载 {len(index)} 个对话")

    def _on_error(self, err):
        self.progress.stop()
        self.set_status("加载失败")
        messagebox.showerror("错误", err)

    def ask_open(self):
        path = filedialog.askopenfilename(
            title="选择 DeepSeek 导出文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self.start_load(path)

    def reload(self):
        path = self.path_var.get().strip()
        if path:
            self.start_load(path)

    def apply_filter(self):
        query = self.search_var.get().strip().lower()
        if query:
            self.filtered = [
                e for e in self.index if query in (e.get("title") or "").lower()
            ]
        else:
            self.filtered = list(self.index)
        if self.newest_first.get():
            self.filtered.sort(
                key=lambda e: e.get("inserted_at") or "", reverse=True
            )
        self.listbox.delete(0, tk.END)
        for e in self.filtered:
            self.listbox.insert(tk.END, f"[{fmt_ts(e.get('inserted_at'))}] {e.get('title')}")

    def on_select(self, event=None):
        sel = self.listbox.curselection()
        if not sel or not self.text:
            return
        entry = self.filtered[sel[0]]
        try:
            conv = load_conversation(self.text, entry)
        except Exception as e:
            messagebox.showerror("解析失败", str(e))
            return
        msgs = ordered_messages(conv.get("mapping") or {})
        self._render(conv, msgs)

    def _render(self, conv, msgs):
        self.view.configure(state=tk.NORMAL)
        self.view.delete("1.0", tk.END)
        self.view.insert(tk.END, f"# {conv.get('title') or ''}\n", "meta")
        self.view.insert(
            tk.END,
            f"创建: {fmt_ts(conv.get('inserted_at'))} | 更新: {fmt_ts(conv.get('updated_at'))}\n\n",
            "meta",
        )
        for i, msg in enumerate(msgs, 1):
            parts, think = split_fragments(msg)
            if not parts and not think:
                continue
            is_user = any(
                f.get("type") == "REQUEST" for f in msg.get("fragments", [])
            )
            role = "用户" if is_user else "助手"
            tag = "user" if is_user else "assistant"
            self.view.insert(
                tk.END,
                f"──────── 第{i}条 · {role} · {fmt_ts(msg.get('inserted_at'))} ────────\n\n",
                tag,
            )
            for p in parts:
                self.view.insert(tk.END, p + "\n\n", tag)
            if think and self.think_var.get():
                self.view.insert(tk.END, f"[思考过程]\n", "think")
                for t in think:
                    self.view.insert(tk.END, t + "\n\n", "think")
        self.view.configure(state=tk.DISABLED)

    def _current_entry(self):
        sel = self.listbox.curselection()
        if not sel or not self.text:
            return None
        return self.filtered[sel[0]]

    def _load_current(self):
        entry = self._current_entry()
        if not entry:
            return None, None, None
        try:
            conv = load_conversation(self.text, entry)
        except Exception as e:
            messagebox.showerror("解析失败", str(e))
            return None, None, None
        return conv, ordered_messages(conv.get("mapping") or {}), entry

    def export_all(self):
        self._export(None, None)

    def export_range(self):
        ans = simpledialog.askstring(
            "导出部分",
            "输入要导出的条数范围，如 3-20（全部请输入 all）:",
            parent=self.root,
        )
        if ans is None:
            return
        ans = ans.strip().lower()
        if ans in ("", "all"):
            self._export(None, None)
            return
        try:
            parts = ans.split("-")
            if len(parts) == 1:
                start = int(parts[0])
                end = int(parts[0])
            else:
                start = int(parts[0])
                end = int(parts[1])
        except ValueError:
            messagebox.showerror("输入无效", "格式示例: 3-20 或 all")
            return
        if start < 1 or end < start:
            messagebox.showerror("输入无效", "范围不正确")
            return
        self._export(start, end)

    def _export(self, start, end):
        conv, msgs, entry = self._load_current()
        if conv is None:
            messagebox.showwarning("提示", "请先选中一个对话")
            return
        path = filedialog.asksaveasfilename(
            title="导出为 Markdown",
            initialfile=(entry.get("title") or "对话") + ".md",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("所有文件", "*.*")],
        )
        if not path:
            return
        md = to_markdown(conv, msgs, self.think_var.get(), start or 1, end)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))
            return
        self.set_status(f"已导出 {len(msgs)} 条对话到 {path}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
