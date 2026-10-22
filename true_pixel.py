"""
兼容入口：python true_pixel.py ... 等同于 python -m truepixel ...

旧用法 `python true_pixel.py --input a.png --output b.png --size 64 --colors 24`
会被自动转换成 `truepixel single a.png b.png --size 64 --colors 24`；
旧的 `--sheet --rows --cols --frames` 会转换成 `truepixel sheet`。
"""
import sys

from truepixel.cli import main


def _translate(argv):
    if not argv or argv[0] in ("single", "batch", "sheet", "tiers", "serve", "-h", "--help"):
        return argv
    args, inp, out, sheet = [], None, None, False
    it = iter(argv)
    for a in it:
        if a in ("--input", "-i"):
            inp = next(it)
        elif a in ("--output", "-o"):
            out = next(it)
        elif a == "--sheet":
            sheet = True
        elif a in ("-c",):
            args += ["--colors", next(it)]
        else:
            args.append(a)
    return (["sheet"] if sheet else ["single"]) + [inp, out] + args


if __name__ == "__main__":
    main(_translate(sys.argv[1:]))
