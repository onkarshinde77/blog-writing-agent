from __future__ import annotations
import requests
import re
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
from src.config import model
from src.schemas import GlobalImagePlan,State
from src.prompts import DECIDE_IMAGES_SYSTEM
load_dotenv()

# helper
def _safe_slug(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9 _-]+", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "blog"     
        
def _generate_image_bytes(prompt: str) -> bytes:
    """Generate image using Pollinations AI and return bytes."""
    prompt = prompt + "\n No cartoon , No anime , only clear image"
    clean_prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true&seed=42"
    print(f"Generating image for: {prompt}...")
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to generate image. Status: {response.status_code}")


# node 1
def merge_content(state: State) -> dict:
    plan = state["plan"]
    if plan is None:
        raise ValueError("merge_content called without plan.")
    ordered_sections = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"
    return {"merged_md": merged_md}

# node 2
def decide_images(state: State) -> dict:
    planner = model.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan = state["plan"]
    assert plan is not None

    image_plan = planner.invoke(
        [
            SystemMessage(content=DECIDE_IMAGES_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {state['topic']}\n\n"
                    "Insert placeholders + propose image prompts.\n\n"
                    f"{merged_md}"
                )
            ),
        ]
    )
    return {
        "md_with_placeholders": image_plan.md_with_placeholders,
        "image_specs": [img.model_dump() for img in image_plan.image],
    }
    

# node 3
def generate_and_place_images(state: State) -> dict:
    plan = state["plan"]
    assert plan is not None

    md = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    # If no images requested, just write merged markdown
    if not image_specs:
        filename = f"{_safe_slug(plan.blog_title)}.md"
        Path(filename).write_text(md, encoding="utf-8")
        return {"final": md}

    images_dir = Path("images")
    images_dir.mkdir(exist_ok=True)

    import base64
    md_disk = md
    md_ui = md

    for spec in image_specs:
        placeholder = spec["placeholder"]
        filename = spec["filename"]
        out_path = images_dir / filename

        img_bytes = None
        # generate only if needed
        if not out_path.exists():
            try:
                img_bytes = _generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
            except Exception as e:
                # graceful fallback: keep doc usable
                prompt_block = (
                    f"> **[IMAGE GENERATION FAILED]** {spec.get('caption','')}\n>\n"
                    f"> **Alt:** {spec.get('alt','')}\n>\n"
                    f"> **Prompt:** {spec.get('prompt','')}\n>\n"
                    f"> **Error:** {e}\n"
                )
                md_disk = md_disk.replace(placeholder, prompt_block)
                md_ui = md_ui.replace(placeholder, prompt_block)
                continue
        else:
            img_bytes = out_path.read_bytes()

        # Update disk version (standard relative link)
        img_disk_md = f"![{spec['alt']}](images/{filename})\n*{spec['caption']}*"
        md_disk = md_disk.replace(placeholder, img_disk_md)
        
        # Update UI version (Base64 injected to trick Streamlit into rendering local files)
        mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        img_ui_md = f"![{spec['alt']}](data:{mime};base64,{b64_data})\n*{spec['caption']}*"
        md_ui = md_ui.replace(placeholder, img_ui_md)

    blog_filename = f"{_safe_slug(plan.blog_title)}.md"
    Path(blog_filename).write_text(md_disk, encoding="utf-8")
    return {"final": md_ui}