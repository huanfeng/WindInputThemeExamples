#!/usr/bin/env python3
"""把「精灵图（2×2 一张）」按配置合成为一个 APNG，并打印各状态的帧区间。

用法：
    python tools/sprites_to_apng.py sources/qingfeng-niang/sprites.toml -o themes/03-skin-animated/assets/actions.png

做三件事：
  1. 按配置从精灵图里取格子，裁切、缩放、清理半透明雾边；
  2. 只有一帧时输出普通 PNG（静态装饰）；否则按「状态 → 帧序列（图, 格, 毫秒）」排成一个 APNG，每帧都是整幅画布、不合并相同帧、不裁子矩形；
  3. 打印每个状态在 APNG 里的帧区间，直接贴进 theme.toml 的 [skin.*.decor.states]。

为什么自己写 APNG 而不用 Pillow 的 save_all：Pillow 会把内容相同的相邻帧合并（帧号整体错位），
还会把帧裁成子矩形；引擎按「原始帧号」引用区间，帧数必须和配置一一对应。
"""
import argparse
import io
import struct
import sys
import tomllib
import zlib
from pathlib import Path

from PIL import Image


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def idat_of(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    data, pos, out = buf.getvalue(), 8, b""
    while pos < len(data):
        length, tag = struct.unpack(">I4s", data[pos : pos + 8])
        if tag == b"IDAT":
            out += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    return out


def write_apng(frames: list[Image.Image], delays_ms: list[int], path: Path) -> None:
    w, h = frames[0].size
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += chunk(b"acTL", struct.pack(">II", len(frames), 0))  # 0 = 无限循环（引擎自己控制循环，不看这个值）
    seq = 0
    for i, (frame, ms) in enumerate(zip(frames, delays_ms)):
        # dispose = BACKGROUND(1)、blend = SOURCE(0)：每帧自成一幅，不依赖上一帧
        out += chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0, ms, 1000, 1, 0))
        seq += 1
        z = idat_of(frame.convert("RGBA"))
        if i == 0:
            out += chunk(b"IDAT", z)
        else:
            out += chunk(b"fdAT", struct.pack(">I", seq) + z)
            seq += 1
    out += chunk(b"IEND", b"")
    path.write_bytes(out)


def load_cell(sheet: Image.Image, cell: int, cfg: dict) -> Image.Image:
    n = cfg["grid"]  # 每边几格，2 = 2×2
    size = sheet.width // n
    row, col = divmod(cell, n)
    im = sheet.crop((col * size, row * size, (col + 1) * size, (row + 1) * size)).convert("RGBA")
    # 清理雾边：alpha 很低的当透明（避免点击命中区被无形的雾撑大），很高的当不透明
    low, high = cfg.get("alpha_low", 12), cfg.get("alpha_high", 245)
    a = im.getchannel("A").point(lambda v: 0 if v <= low else (255 if v >= high else v))
    im.putalpha(a)
    im = im.crop(tuple(cfg["crop"]))  # 所有格子共用同一个裁切框，帧间才不会抖
    s = cfg.get("scale", 1.0)
    if s != 1.0:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return im


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    cfg = tomllib.loads(args.config.read_text(encoding="utf-8"))
    base = args.config.parent
    sheets: dict[str, Image.Image] = {}
    for sid, rel in cfg["sheets"].items():
        sheets[sid] = Image.open(base / rel)

    frames: list[Image.Image] = []
    delays: list[int] = []
    ranges: list[tuple[str, int, int]] = []
    for name, state in cfg["states"].items():
        first = len(frames)
        for sheet_id, cell, ms in state["frames"]:
            sheet_id = str(sheet_id)
            if sheet_id not in sheets:
                sys.exit(f"状态 {name} 引用了不存在的精灵图 {sheet_id!r}，已定义：{sorted(sheets)}")
            frames.append(load_cell(sheets[sheet_id], cell, cfg["grid"]))
            delays.append(ms)
        ranges.append((name, first, len(frames) - 1))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if len(frames) == 1:  # 单帧 = 静态装饰图，直接存普通 PNG
        frames[0].save(args.output, "PNG", optimize=True)
    else:
        write_apng(frames, delays, args.output)
    size_mb = args.output.stat().st_size / 1e6
    print(f"{args.output}：{len(frames)} 帧，画布 {frames[0].width}×{frames[0].height}，{size_mb:.2f} MB")
    if size_mb > 15:
        print("警告：单个图片上限 16 MiB，接近上限；减少帧数或缩小 scale。", file=sys.stderr)
    print("\n# 贴进 theme.toml：")
    for name, a, b in ranges:
        print(f'{name} = {{ frames = "{a}-{b}" }}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
