#!/usr/bin/env python3
"""检查主题目录：引用的图片在不在、动画帧区间有没有越界、基本字段是否齐全。

用法：python tools/check_theme.py themes/03-skin-animated

只做「肉眼最容易漏掉的」那几项，不替代输入法的真正校验（那个以导入时为准）：
  - theme.toml 能解析，[meta] 有 name；
  - 所有 image = "..." 指向的文件都存在，且在 assets/ 下；
  - 动画装饰：states / on 里的帧区间不超过该图的帧数；on 里引用的状态名存在；
  - 事件名拼写（只认引擎支持的）。
"""
import re
import sys
import tomllib
from pathlib import Path

from PIL import Image

EVENTS = {"show", "hide", "typing", "backspace", "page", "empty", "commit", "mode_cn", "mode_en", "click"}


def frame_count(path: Path) -> int:
    try:
        with Image.open(path) as im:
            return getattr(im, "n_frames", 1)
    except Exception:
        return -1


def clip_range(v) -> tuple[int, int] | None:
    """'a-b' / 'a' / 整数 / { frames = .. } / { image = .. } → 帧区间；image 片段返回 None。"""
    if isinstance(v, dict):
        if "frames" not in v:
            return None
        v = v["frames"]
    if isinstance(v, int):
        return v, v
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(v))
    if not m:
        return (-1, -1)
    a = int(m.group(1))
    return a, int(m.group(2) or a)


def walk_decors(skin: dict):
    for variant in ("horizontal", "vertical", "horizontal_embedded", "vertical_embedded"):
        for d in (skin.get(variant) or {}).get("decor", []) or []:
            yield variant, d


def check(theme_dir: Path) -> list[str]:
    out: list[str] = []
    path = theme_dir / "theme.toml"
    if not path.is_file():
        return [f"错误：{path} 不存在"]
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        return [f"错误：theme.toml 解析失败：{e}"]
    if not doc.get("meta", {}).get("name"):
        out.append("错误：缺 [meta] name")

    skin = doc.get("skin") or {}
    resources = doc.get("resources") or {}

    def resolve(ref: str) -> Path:
        r = resources.get(ref, ref)
        if isinstance(r, dict):  # light / dark 变体
            r = r.get("light") or r.get("dark") or ""
        return theme_dir / r

    def check_image(ref: str, where: str):
        if ref.startswith("data:"):
            return
        p = resolve(ref)
        if not p.is_file():
            out.append(f"错误：{where} 引用的图片不存在：{p}")
        elif "assets" not in p.relative_to(theme_dir).parts[:1]:
            out.append(f"错误：{where} 的图片不在 assets/ 下：{ref}")

    for variant in ("horizontal", "vertical", "horizontal_embedded", "vertical_embedded"):
        v = skin.get(variant)
        if not v:
            continue
        frame = (v.get("frame") or {}).get("image")
        if frame:
            check_image(frame, f"skin.{variant}.frame")
        for i, d in enumerate(v.get("decor", []) or []):
            where = f"skin.{variant}.decor[{i}]"
            img = d.get("image")
            if not img:
                out.append(f"错误：{where} 缺 image")
                continue
            check_image(img, where)
            n = frame_count(resolve(img)) if not img.startswith("data:") else 1
            states = d.get("states") or {}
            for name, clip in states.items():
                r = clip_range(clip)
                if r and (r[0] < 0 or r[0] > r[1] or r[1] >= n):
                    out.append(f"错误：{where}.states.{name} 帧区间 {clip} 越界（图只有 {n} 帧）")
            for ev, act in (d.get("on") or {}).items():
                if ev not in EVENTS and not re.fullmatch(r"idle_\d+s", ev):
                    out.append(f"错误：{where}.on 未知事件 {ev!r}（支持：{sorted(EVENTS)} 与 idle_<N>s）")
                    continue
                for a in [act, *(act.get("alt", []) if isinstance(act, dict) else [])]:
                    if not isinstance(a, dict):
                        out.append(f"错误：{where}.on.{ev} 写法不对")
                        continue
                    if "state" in a and a["state"] not in states:
                        out.append(f"错误：{where}.on.{ev} 引用了不存在的状态 {a['state']!r}")
                    if "play" in a:
                        r = clip_range(a["play"])
                        if r and (r[0] < 0 or r[0] > r[1] or r[1] >= n):
                            out.append(f"错误：{where}.on.{ev} play {a['play']} 越界（图只有 {n} 帧）")
                    t = a.get("then")
                    if t not in (None, "@prev") and t not in states:
                        out.append(f"错误：{where}.on.{ev} then 引用了不存在的状态 {t!r}")
                if isinstance(act, dict) and ("alt" in act or "lock" in act):
                    out.append(f"提示：{where}.on.{ev} 用了 alt / lock（0.133 起；旧版本忽略它们，按主条播放）")
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    problems = check(Path(sys.argv[1]))
    for p in problems:
        print(p)
    errors = [p for p in problems if p.startswith("错误")]
    print(f"\n{'通过' if not errors else '未通过'}：{len(errors)} 个错误，{len(problems) - len(errors)} 条提示")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
