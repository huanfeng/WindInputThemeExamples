# 做一个主题的完整流程

```
设计角色 ─▶ 画窗体框架 ─▶ 画人物（静态 / 动作精灵图）─▶ 合成动画 ─▶ 写配置 ─▶ 检查 ─▶ 本机试用 ─▶ 打包 ─▶ 发布
 prompts/10   prompts/20     prompts/31 / 30               tools/        prompts/50   tools/      输入法        tools/      主题市场
                                                            sprites_to_apng           check_theme              pack_wtheme
```

## 0. 准备

```sh
pip install -r tools/requirements.txt   # 只需要 Pillow；Python 3.11+
```

## 1. 起步：复制最近的示例

| 目标 | 复制 |
|---|---|
| 换色 | `themes/01-color` |
| 静态皮肤 | `themes/02-skin-static` |
| 动态皮肤 | `themes/03-skin-animated` + `sources/qingfeng-niang` |

目录名随意（用英文/拼音，不要空格）；`theme.toml` 里 `[meta] name` 才是显示名。

## 2. 素材

按 `prompts/` 里的模板生成，规格和稳定性要点都写在模板里。素材放：

- 主题运行时需要的图 → `themes/<你的主题>/assets/`
- 动画的原始精灵图（可再加工的源码）→ `sources/<你的主题>/sheets/`，不进主题包

## 3. 合成动画（只有动态主题需要）

```sh
python tools/sprites_to_apng.py sources/<你的主题>/sprites.toml -o themes/<你的主题>/assets/actions.png
```

脚本打印每个状态的帧区间，贴进 `theme.toml` 的 `[skin.*.decor.states]`；
改节奏、换格子、调顺序只改 `sprites.toml`，重新运行即可。

## 4. 写配置

`theme.toml`。静态皮肤的注释最全：`themes/02-skin-static/theme.toml`；
动画事件的写法看 `themes/03-skin-animated/theme.toml` 头部。也可以交给 AI 起草（[prompts/50](../prompts/50-让AI写皮肤配置.md)）。

## 5. 检查

```sh
python tools/check_theme.py themes/<你的主题>
```

检查引用的图片是否存在、动画帧区间是否越界、事件名/状态名是否写对。它不替代输入法自己的校验。

## 6. 本机试用

把主题目录复制到输入法的用户主题目录，在设置里选择：

- Windows：`%APPDATA%\WindInput\themes\<主题目录>\`（Dev 版是 `WindInputDev`）

改完 `theme.toml` 或图片后，在设置里重选一次主题即可重新加载。

## 7. 打包

```sh
python tools/pack_wtheme.py themes/<你的主题> -o dist/<你的主题>.wtheme --preview preview.png
```

`.wtheme` 是 zip：`theme.toml`、`assets/**`、自动生成的 `package.toml`，以及可选的 `preview.png`（市场展示图）。
也可以在输入法设置里直接「导出主题包」。限制：条目 ≤ 200、单个图片 ≤ 16 MiB、解压后总量 ≤ 64 MiB。

**`.wtheme` 不包含**：

- 父主题 `_qingfeng`（它是内置的，使用者安装的版本里有）；
- 动画精灵图原稿与合成配置——想让别人能二次创作，把 `sources/<你的主题>/` 一并公开。

## 8. 发布

在主题市场（market.windinput.com）上传 `.wtheme`。上传前确认素材授权与署名。

## 版本兼容

主题格式只加不减：新字段旧版本会忽略。写主题时，把「旧版本也能正常工作」的写法放在主条里，新特性放在旧版本会忽略的字段中。
例如 `click` 的 `alt` / `lock`（0.133 起）：旧版本只播主条，不随机、可被打断，其余照常。
