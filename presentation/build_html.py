# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown", "pygments"]
# ///
"""
Build a single-file HTML presentation from DemystifyingTheGIL.md.

Run from the project root with:
    uv run presentation/build_html.py

Output: presentation/DemystifyingTheGIL.html

Navigation: left/right arrow keys.
"""

import base64
import re
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

HERE = Path(__file__).parent


def encode_image(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    if ext == "jpg":
        ext = "jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{ext};base64,{data}"


def extract_region(code: str, region: str) -> str:
    pattern = (
        rf"#\s*region\s+{re.escape(region)}\s*\n"
        rf"(.*?)"
        rf"#\s*endregion\s+{re.escape(region)}"
    )
    m = re.search(pattern, code, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    return code


def resolve_include(directive: str, base_dir: Path) -> str:
    spec = directive.replace("<<<", "", 1).strip()
    spec = re.sub(r"\s*\{[^}]*\}\s*$", "", spec).strip()
    if "#" in spec:
        filepath, region = spec.split("#", 1)
    else:
        filepath, region = spec, None
    full_path = (base_dir / filepath.strip()).resolve()
    code = full_path.read_text(encoding="utf-8")
    if region:
        code = extract_region(code, region.strip())
    lang = full_path.suffix.lstrip(".") or "text"
    return f"```{lang}\n{code}\n```"


def is_frontmatter_line(s: str) -> bool:
    if not s or s[0] in (" ", "\t"):
        return False
    if ":" not in s:
        return False
    key = s.split(":", 1)[0].strip()
    return bool(key) and all(c.isalnum() or c in "_-" for c in key)


def parse_slides(text: str):
    """Split Slidev-flavored markdown into a list of {meta, content} dicts."""
    lines = text.splitlines()
    slides = []
    i = 0

    # Skip global frontmatter
    if i < len(lines) and lines[i].strip() == "---":
        i += 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1

    while i < len(lines):
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break

        meta = {}
        content_lines = []

        if lines[i].strip() == "---":
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and is_frontmatter_line(lines[j]):
                i = j
                while i < len(lines) and lines[i].strip() != "---":
                    if is_frontmatter_line(lines[i]):
                        k, v = lines[i].split(":", 1)
                        meta[k.strip()] = v.strip()
                    i += 1
                if i < len(lines):
                    i += 1  # past closing ---
            else:
                i += 1  # bare separator
                continue

        while i < len(lines) and lines[i].strip() != "---":
            content_lines.append(lines[i])
            i += 1

        slides.append({
            "meta": meta,
            "content": "\n".join(content_lines).strip(),
        })
        # Don't consume the trailing ---; next iteration handles it.

    return [s for s in slides if s["meta"] or s["content"]]


def process_content(content: str, base_dir: Path) -> str:
    new_lines = []
    for line in content.split("\n"):
        if line.strip().startswith("<<<"):
            new_lines.append(resolve_include(line.strip(), base_dir))
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


def render_slide(slide, base_dir: Path) -> str:
    meta = slide["meta"]
    if meta.get("layout") == "image":
        img = meta.get("image", "")
        if img:
            img_path = (base_dir / img).resolve()
            data_url = encode_image(img_path)
            return f'<section class="slide image-slide"><img src="{data_url}"></section>'

    content = process_content(slide["content"], base_dir)
    md = markdown.Markdown(extensions=["fenced_code", "tables", "codehilite"])
    html = md.convert(content)
    return f'<section class="slide">{html}</section>'


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Demystifying The GIL</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{
    margin: 0; padding: 0;
    height: 100%; width: 100%;
    overflow: hidden;
    background: #fff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    color: #222;
}}
.slide {{
    display: none;
    position: absolute;
    inset: 0;
    padding: 4vh 8vw;
    overflow: auto;
    font-size: 2.2vh;
    line-height: 1.4;
}}
.slide.active {{ display: block; }}
.image-slide {{ padding: 0; }}
.image-slide img {{
    width: 100%; height: 100%;
    object-fit: contain;
    display: block;
}}
h1 {{ font-size: 2.6em; margin: 0 0 0.6em; }}
h2 {{ font-size: 1.8em; }}
ul, ol {{ font-size: 1.3em; line-height: 1.5; padding-left: 1.5em; }}
li {{ margin-bottom: 0.4em; }}
p {{ font-size: 1.3em; }}
pre {{
    background: #f5f5f5; padding: 0.8em 1em;
    border-radius: 6px; overflow-x: auto;
    font-size: 0.95em; line-height: 1.3;
}}
code {{ font-family: "Fira Code", Consolas, Monaco, monospace; }}
:not(pre) > code {{
    background: #f0f0f0; padding: 0.1em 0.3em;
    border-radius: 3px; font-size: 0.95em;
}}
table {{ border-collapse: collapse; font-size: 1.15em; margin: 0.5em 0; }}
th, td {{ padding: 0.3em 0.9em; border-bottom: 1px solid #ddd; text-align: left; }}
th {{ background: #f0f0f0; }}
blockquote {{
    border-left: 4px solid #666;
    padding: 0.3em 1em;
    margin: 1em 0;
    color: #333;
    font-size: 1.3em;
}}
{code_css}
</style>
</head>
<body>
{slides}
<script>
const slides = document.querySelectorAll('.slide');
let current = 0;
function show(i) {{
    slides.forEach((s, idx) => s.classList.toggle('active', idx === i));
}}
show(0);
document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowRight' && current < slides.length - 1) {{
        current++; show(current);
    }} else if (e.key === 'ArrowLeft' && current > 0) {{
        current--; show(current);
    }}
}});
</script>
</body>
</html>
"""


def translate_slidev_css(css: str) -> str:
    """Translate Slidev-specific class selectors to our HTML class selectors.

    The original style.css targets Slidev's classes (.slidev-code, .shiki,
    .slidev-layout). The generated HTML uses Pygments + our own .slide class,
    so rewrite the selectors to match.
    """
    return (
        css.replace(".slidev-code .shiki", ".codehilite")
        .replace(".slidev-code .line.highlighted", ".codehilite .hll")
        .replace(".slidev-code .line.dishonored", ".codehilite .line-dishonored")
        .replace(".slidev-code", ".codehilite")
        .replace(".shiki span", ".codehilite span")
        .replace(".shiki", ".codehilite")
        .replace(".slidev-layout", ".slide")
    )


def build_html(md_path: Path) -> str:
    md_content = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent
    slides = parse_slides(md_content)
    rendered = "\n".join(render_slide(s, base_dir) for s in slides)
    code_css = HtmlFormatter(style="default").get_style_defs(".codehilite")
    user_css_path = base_dir / "style.css"
    user_css = ""
    if user_css_path.exists():
        user_css = "\n/* from style.css */\n" + translate_slidev_css(
            user_css_path.read_text(encoding="utf-8")
        )
    return HTML_TEMPLATE.format(
        code_css=code_css + user_css, slides=rendered
    )


def main():
    md_path = HERE / "DemystifyingTheGIL.md"
    out_path = HERE / "DemystifyingTheGIL.html"
    html = build_html(md_path)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(html):,} bytes, {out_path.stat().st_size:,} on disk)")


if __name__ == "__main__":
    main()
