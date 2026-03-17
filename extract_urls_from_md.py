from pathlib import Path
import re


source = Path(input("请输入 md 文件路径: ").strip())
target = source.parent / (source.stem + "_urls.txt")

lines = source.read_text(encoding="utf-8").splitlines()
text = "\n".join(lines[12:])
urls = re.findall(r"https?://[^\s<>)\]\"]+", text)

target.write_text("\n".join(urls), encoding="utf-8")
print(f"wrote {len(urls)} urls to {target}")
