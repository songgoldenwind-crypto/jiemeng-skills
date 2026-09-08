# 解梦 Agent Skill

一个面向 Codex 及兼容 Agent Skills 客户端的中文解梦 Skill。它从梦中对象、动作、状态、方向和结果检索传统梦兆，可选扩查用户持有的《梦林玄解》扫描本，再结合梦境情节与现实语境作审慎解释。

## 特点

- 内置 27 个传统梦象门类、951 个原始文本片段。
- 支持将用户持有的 369 页《梦林玄解》建成本机私有 OCR 索引。
- 纳入全梦迁变、明暗/完损反转、梦者处境和信息不足时降级等方法。
- 区分精确匹配、近似匹配、类比和无直接条目。
- 多个梦象沿主事件链解释，不按吉凶条目数量投票。
- 对古籍抄本中的疑似错字、缺字和条目粘连保留原貌并提示降级。
- 将传统梦兆、语境推断和现实事实分开。
- 不凭梦境诊断疾病、预告死亡、判断怀孕、指认出轨或提供投资依据。

## 安装

克隆仓库后运行安装器：

```bash
git clone https://github.com/songgoldenwind-crypto/jiemeng-skills.git
cd jiemeng-skills
python3 scripts/install.py --agent codex --scope user
```

默认的开放标准安装位置是 `~/.agents/skills/`：

```bash
python3 scripts/install.py
```

也可以直接复制：

```bash
cp -R skills/dream-interpretation ~/.codex/skills/
```

安装器还支持 Claude Code、Cursor、Gemini CLI、GitHub Copilot、OpenCode、Windsurf、Cline，以及自定义目录：

```bash
python3 scripts/install.py --agent all --scope user
python3 scripts/install.py --agent custom --destination /path/to/skills
```

已存在同名目录时，安装器会拒绝覆盖；确认替换时显式添加 `--force`。

## 使用

可以显式调用：

```text
使用 $dream-interpretation 解读：我梦见一条蛇从门口进入屋里，然后咬了我。
```

也可以直接描述梦境或查询传统条目：

```text
我梦见牙齿掉了，按传统说法怎么解释？
什么梦在传统条目里与发财有关？
```

Skill 会优先使用梦里的具体动作与状态。例如“蛇入门”“蛇咬人”“蛇随人去”不会被合并成同一个“梦见蛇”的固定答案。

## 条目检索

检索脚本不依赖第三方包：

```bash
python3 skills/dream-interpretation/scripts/search_dreams.py \
  --query "梦见井水" \
  --max-results 8
```

输出包含门类、原条目、原文件逻辑行号、匹配范围和文本质量警告。使用 `--list-categories` 查看全部门类，使用 `--category` 限定检索范围。

## 《梦林玄解》本地索引

仓库不分发原 PDF 或整书 OCR。如果你合法持有该书的扫描本，可以在本机一次性建立可恢复的 OCR 索引：

```bash
python3 skills/dream-interpretation/scripts/build_menglin_index.py \
  "/path/to/梦林玄解.pdf"
```

默认索引位于 `~/.local/share/jiemeng-skills/menglin-xuanjie/`。建立时需要 Poppler 的 `pdfinfo`/`pdftoppm`、Tesseract 及 `chi_sim` 语言包。脚本会校验已登记扫描件的 SHA-256，中断后重跑会继续未完成页。

检查状态或检索：

```bash
python3 skills/dream-interpretation/scripts/search_menglin.py --status
python3 skills/dream-interpretation/scripts/search_menglin.py \
  --query "水浑浊后变清" \
  --max-results 6
```

检索器只返回有限长度的 OCR 片段和 PDF/书页定位。OCR 会错字，决定解释方向的原句应回看页图。

## 仓库结构

```text
.
├── skills/dream-interpretation/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/
│   └── scripts/
├── scripts/
├── tests/
└── LICENSE
```

## 验证与打包

```bash
python3 scripts/validate_repo.py
python3 skills/dream-interpretation/scripts/test_search.py
python3 skills/dream-interpretation/scripts/test_menglin.py
python3 tests/test_distribution.py
python3 scripts/package_skill.py
```

打包脚本会在 `dist/` 生成：

- `dream-interpretation.skill`：`SKILL.md` 位于压缩包根目录；
- `dream-interpretation.zip`：包含 `dream-interpretation/` 外层目录。

## 资料说明

内置辞典来自传统梦兆抄本的机械整理版本。《梦林玄解》通道只公开来源指纹、检索工具与原创方法提炼，完整 OCR 仅留在用户本机。仓库不宣称传统梦兆具有经过验证的预测能力；它们作为民俗材料参与解释。仓库中的代码、Skill 指令、检索逻辑和原创说明按 MIT License 开源。

## License

[MIT](LICENSE)
