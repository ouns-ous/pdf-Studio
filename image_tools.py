"""Shared image preparation for previews and exported PDF pages."""
from PIL import Image, ImageOps


class ImageLayoutError(ValueError):
    pass


def validate_image_margin(width, height, margin):
    if width <= margin * 2 or height <= margin * 2:
        raise ImageLayoutError(
            "Margins are too large for this image. Choose A4 or smaller margins, then update preview."
        )


def page_image(source):
    image = ImageOps.exif_transpose(source)
    if "A" in image.getbands() or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")
