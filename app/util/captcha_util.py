import base64
import io
from app.core.logging import get_logger
import random
import uuid

from PIL import Image, ImageDraw, ImageFont

logger = get_logger(__name__)

_CACHED_FONT: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font(size: int = 36) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _CACHED_FONT
    if _CACHED_FONT is not None:
        return _CACHED_FONT

    _font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/msyhbd.ttc",
    ]
    for path in _font_candidates:
        try:
            _CACHED_FONT = ImageFont.truetype(path, size)
            logger.info(f"Captcha font loaded from: {path}")
            return _CACHED_FONT
        except OSError:
            continue

    logger.warning(
        "No system TrueType font found for captcha. "
        "Falling back to Pillow default bitmap font. "
        "Image quality may be degraded."
    )
    try:
        _CACHED_FONT = ImageFont.load_default(size=size)
    except TypeError:
        _CACHED_FONT = ImageFont.load_default()
    return _CACHED_FONT


def _random_light_color() -> tuple[int, int, int]:
    return (random.randint(230, 255), random.randint(230, 255), random.randint(230, 255))


def _random_dark_color() -> tuple[int, int, int]:
    return (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))


def _random_mid_color() -> tuple[int, int, int]:
    return (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))


def generate_math_captcha() -> dict:
    op_char = random.choice(["+", "-", "x"])
    if op_char == "+":
        a = random.randint(1, 30)
        b = random.randint(1, 30)
        answer = a + b
    elif op_char == "-":
        a = random.randint(2, 30)
        b = random.randint(1, a)
        answer = a - b
    else:
        a = random.randint(1, 12)
        b = random.randint(1, 12)
        answer = a * b

    expression = f"{a} {op_char} {b} = ?"
    captcha_key = uuid.uuid4().hex[:16]

    width, height = 200, 70
    img = Image.new("RGB", (width, height), color=_random_light_color())
    draw = ImageDraw.Draw(img)
    font = _get_font(36)

    x_cursor = 15
    y_base = random.randint(12, 18)
    for char in expression:
        x_cursor += random.randint(0, 3)
        y_char = y_base + random.randint(-3, 3)
        draw.text((x_cursor, y_char), char, fill=_random_dark_color(), font=font)
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        x_cursor += char_width + random.randint(1, 4)

    for _ in range(random.randint(3, 5)):
        draw.line(
            [
                (random.randint(0, width), random.randint(0, height)),
                (random.randint(0, width), random.randint(0, height)),
            ],
            fill=_random_mid_color(),
            width=1,
        )

    for _ in range(random.randint(50, 100)):
        draw.point(
            (random.randint(0, width - 1), random.randint(0, height - 1)),
            fill=_random_mid_color(),
        )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return {
        "captcha_key": captcha_key,
        "captcha_image": f"data:image/png;base64,{base64_str}",
        "_answer": answer,
    }
