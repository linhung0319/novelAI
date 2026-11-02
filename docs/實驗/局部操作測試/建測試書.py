"""複製 雁門鏢-測試 成 局部操作-測試，並 git init（不 commit），寫入測試不會碰到原書。

用法：python 建測試書.py        已存在就中止
      python 建測試書.py --reset 刪掉重建
"""
import pathlib
import shutil
import stat
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
BOOKS = pathlib.Path(__file__).resolve().parents[4] / "novel-desk" / "books"
SRC = BOOKS / "雁門鏢-測試"
DST = BOOKS / "局部操作-測試"


def force(func, path, _):
    pathlib.Path(path).chmod(stat.S_IWRITE)
    func(path)


def main():
    if DST.exists():
        if "--reset" not in sys.argv:
            sys.exit(f"已存在：{DST}")
        shutil.rmtree(DST, onerror=force)
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns(".git"))
    subprocess.run(["git", "init", "-q"], cwd=DST, check=True)
    print("完成", DST)


if __name__ == "__main__":
    main()
