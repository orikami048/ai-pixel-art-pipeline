# skills/

给生图 AI 用的 skill。仓库里这份是正本，改完再复制到 AI 的 skill 目录。

| skill | 用途 |
|---|---|
| `truepixel-imagegen` | 像素风游戏素材：生图提示词规则 + TruePixel 后处理命令 + 验收清单 |

## 安装

Antigravity（Gemini）全局 skill 目录是 `~/.gemini/config/skills/`：

```powershell
Copy-Item -Recurse -Force skills\truepixel-imagegen $env:USERPROFILE\.gemini\config\skills\
```

Claude Code 用户级 skill 目录是 `~/.claude/skills/`，复制方法一样。
