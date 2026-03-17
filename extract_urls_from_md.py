from pathlib import Path
import re


def extract_urls_from_md_file(md_path: str | Path) -> tuple[Path, int]:
    """从 markdown 文件提取所有 URL 到同目录下的 _urls.txt 文件，返回 (txt 路径, url 数量)"""
    source = Path(md_path)
    target = source.parent / (source.stem + "_urls.txt")

    lines = source.read_text(encoding="utf-8").splitlines()
    text = "\n".join(lines[12:])
    urls = re.findall(r"https?://[^\s<>)\]\"]+", text)

    target.write_text("\n".join(urls), encoding="utf-8")
    return target, len(urls)


if __name__ == "__main__":
    source = Path(input("请输入 md 文件路径: ").strip())
    target, count = extract_urls_from_md_file(source)
    print(f"wrote {count} urls to {target}")
