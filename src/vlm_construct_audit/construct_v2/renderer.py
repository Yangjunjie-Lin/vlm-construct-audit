"""Deterministic flat-shape renderer with no model-visible identifiers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
RGB = {
    "red": "#d73027", "blue": "#2878b5", "green": "#249152", "amber": "#e6a700",
    "violet": "#7651b5", "coral": "#e76f51", "teal": "#168a8a", "indigo": "#3f51b5",
    "gold": "#c99a00", "pink": "#d45a9c", "brown": "#8b5a2b", "gray": "#727272",
}


def _polygon(cx: int, cy: int, radius: int, sides: int, rotation: float = -math.pi / 2) -> list[tuple[float, float]]:
    return [
        (cx + radius * math.cos(rotation + 2 * math.pi * i / sides),
         cy + radius * math.sin(rotation + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


def _draw_shape(draw: ImageDraw.ImageDraw, entity: dict[str, Any]) -> None:
    x, y, radius = int(entity["x"]), int(entity["y"]), 22
    color = RGB[entity["color"]]
    shape = entity["shape"]
    box = (x - radius, y - radius, x + radius, y + radius)
    outline = "#161616"
    if shape in {"circle", "oval", "crescent"}:
        if shape == "oval":
            box = (x - radius - 6, y - radius + 5, x + radius + 6, y + radius - 5)
        draw.ellipse(box, fill=color, outline=outline, width=3)
        if shape == "crescent":
            draw.ellipse((x - 5, y - radius, x + radius + 7, y + radius), fill="#f4f4f1")
    elif shape == "square":
        draw.rectangle(box, fill=color, outline=outline, width=3)
    elif shape == "triangle":
        draw.polygon(_polygon(x, y, radius + 2, 3), fill=color, outline=outline)
    elif shape == "diamond":
        draw.polygon(_polygon(x, y, radius + 2, 4), fill=color, outline=outline)
    elif shape == "star":
        points = []
        for i in range(10):
            r = radius + 3 if i % 2 == 0 else radius // 2
            angle = -math.pi / 2 + i * math.pi / 5
            points.append((x + r * math.cos(angle), y + r * math.sin(angle)))
        draw.polygon(points, fill=color, outline=outline)
    elif shape == "cross":
        w = 8
        points = [(x-w,y-radius),(x+w,y-radius),(x+w,y-w),(x+radius,y-w),
                  (x+radius,y+w),(x+w,y+w),(x+w,y+radius),(x-w,y+radius),
                  (x-w,y+w),(x-radius,y+w),(x-radius,y-w),(x-w,y-w)]
        draw.polygon(points, fill=color, outline=outline)
    elif shape == "trapezoid":
        draw.polygon([(x-14,y-radius),(x+14,y-radius),(x+radius,y+radius),
                      (x-radius,y+radius)], fill=color, outline=outline)
    else:
        sides = {"pentagon": 5, "hexagon": 6, "octagon": 8}.get(shape, 6)
        draw.polygon(_polygon(x, y, radius + 2, sides), fill=color, outline=outline)


def render_scene(row: dict[str, Any], *, irrelevant_control: bool = False) -> Path:
    image_spec = row["image"]
    key = "irrelevant_render_entities" if irrelevant_control else "render_entities"
    entities = image_spec.get(key, image_spec["render_entities"])
    relative = image_spec.get("irrelevant_control_path") if irrelevant_control else image_spec["path"]
    if relative is None:
        raise ValueError("scene has no irrelevant control image")
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (256, 256), "#f4f4f1")
    draw = ImageDraw.Draw(image)
    for entity in entities:
        _draw_shape(draw, entity)
    image.save(target, format="PNG", optimize=False)
    return target


def render_dataset(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        render_scene(row)
        count += 1
        if row["image"].get("irrelevant_control_path"):
            render_scene(row, irrelevant_control=True)
            count += 1
    return count

