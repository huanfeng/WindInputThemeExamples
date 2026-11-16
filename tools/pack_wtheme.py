#!/usr/bin/env python3
"""把主题目录打成 .wtheme 主题包（格式与输入法设置端「导出主题包」一致）。

用法：
    python tools/pack_wtheme.py themes/03-skin-animated -o dist/qingfeng-niang.wtheme [--preview preview.png]

包里只收 theme.toml 和 assets/**，加上自动生成的 package.toml（名称/作者/版本取自 theme.toml 的 [meta]）。
图片用 zip 存储模式（不再压缩），文本用 deflate。
打包前先跑 check_theme.py 的检查；导入时设置端还会按同一套上限再校验一遍：
    条目 ≤ 200，单个图片 ≤ 16 MiB，解压后总量 ≤ 64 MiB。
"""
import argparse
import sys
import tomllib
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_theme import check  # noqa: E402

MAX_ENTRIES = 200
MAX_IMAGE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
STORED_EXT = {".png", ".webp", ".gif", ".jpg", ".jpeg"}


def toml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme_dir", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--preview", type=Path, help="市场预览图 preview.png（可选）")
    args = ap.parse_args()

    problems = check(args.theme_dir)
    errors = [p for p in problems if p.startswith("错误")]
    for p in problems:
        print(p, file=sys.stderr)
    if errors:
        return 1

    theme_text = (args.theme_dir / "theme.toml").read_text(encoding="utf-8")
    meta = tomllib.loads(theme_text).get("meta", {})
    package_toml = (
        "[package]\nformat_version = 1\nkind = \"theme\"\n"
        f"name = {toml_str(meta.get('name', ''))}\n"
        f"author = {toml_str(meta.get('author', ''))}\n"
        f"version = {toml_str(meta.get('version', ''))}\n"
    )

    assets = sorted(p for p in (args.theme_dir / "assets").rglob("*") if p.is_file()) if (args.theme_dir / "assets").is_dir() else []
    entries = 2 + (1 if args.preview else 0) + len(assets)
    if entries > MAX_ENTRIES:
        sys.exit(f"条目过多：{entries} > {MAX_ENTRIES}")
    total = len(package_toml) + len(theme_text.encode())
    for a in assets:
        n = a.stat().st_size
        if n > MAX_IMAGE:
            sys.exit(f"资源过大：{a}（{n} 字节，单个上限 {MAX_IMAGE}）")
        total += n
    if total > MAX_TOTAL:
        sys.exit(f"总量过大：{total} > {MAX_TOTAL}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w") as z:
        z.writestr("package.toml", package_toml, zipfile.ZIP_DEFLATED)
        z.writestr("theme.toml", theme_text, zipfile.ZIP_DEFLATED)
        if args.preview:
            z.write(args.preview, "preview.png", zipfile.ZIP_STORED)
        for a in assets:
            rel = "assets/" + a.relative_to(args.theme_dir / "assets").as_posix()
            z.write(a, rel, zipfile.ZIP_STORED if a.suffix.lower() in STORED_EXT else zipfile.ZIP_DEFLATED)
    print(f"{args.output}：{entries} 个条目，{args.output.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
