"""First-frame Pillow conversions and explicit image edits."""

from PIL import Image, ImageOps
import pillow_heif

from ..core.formats import sorted_items

pillow_heif.register_heif_opener()
ENCODERS = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "avif": "AVIF", "tiff": "TIFF", "ico": "ICO", "pdf": "PDF", "heic": "HEIF", "bmp": "BMP", "gif": "GIF"}
SUFFIXES = {"compress": "compressed", "half": "smaller", "max1920": "1920", "rotate.right": "rotated", "rotate.left": "rotated", "flip": "mirrored", "square": "square", "grayscale": "grayscale", "strip": "no metadata"}


def load(path, context):
    with Image.open(path) as source:
        if getattr(source, "n_frames", 1) > 1:
            context.result.notes.append(f"{path.name}: only the first frame was used")
        source.seek(0)
        oriented = ImageOps.exif_transpose(source)
        image = oriented.copy()
        if oriented is not source:
            oriented.close()
    return image


def flatten(image):
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", image.size, "white")
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    rgba.close()
    return canvas


def edit(image, name):
    edits = {"half": halve, "max1920": fit1920, "rotate.right": rotate_right, "rotate.left": rotate_left, "flip": ImageOps.mirror, "square": square, "grayscale": ImageOps.grayscale, "strip": copy_image, "compress": copy_image}
    if name not in edits:
        raise ValueError(f"Unsupported image edit: {name}")
    return edits[name](image)


def copy_image(image):
    return image.copy()


def halve(image):
    return image.resize((max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.LANCZOS)


def fit1920(image):
    result = image.copy()
    result.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
    return result


def rotate_right(image):
    return image.transpose(Image.Transpose.ROTATE_270)


def rotate_left(image):
    return image.transpose(Image.Transpose.ROTATE_90)


def square(image):
    size = min(image.size)
    left, top = (image.width - size) // 2, (image.height - size) // 2
    return image.crop((left, top, left + size, top + size))


def save_options(target, quality, compress):
    options = {}
    if target in {"jpg", "webp", "avif", "heic", "pdf"}:
        options["quality"] = quality
    if target == "jpg":
        options.update(progressive=True, subsampling=2)
    if target == "png":
        options["compress_level"] = 9 if compress else 6
    return options


def save(image, path, target, quality, compress=False, strip=False):
    if target not in ENCODERS:
        raise ValueError(f"Unsupported image output: {target}")
    prepared = prepare(image, target, compress)
    try:
        options = save_options(target, quality, compress)
        if not strip:
            options.update(metadata_options(image, target))
        if target == "ico":
            options["sizes"] = [(size, size) for size in (16, 32, 48, 64, 128, 256) if size <= max(prepared.size)]
        prepared.save(path, format=ENCODERS[target], **options)
    finally:
        prepared.close()


def metadata_options(image, target):
    if target not in {"jpg", "png", "webp", "tiff", "heic", "avif"}:
        return {}
    return {key: image.info[key] for key in ("exif", "icc_profile", "xmp") if image.info.get(key)}


def prepare(image, target, compress):
    if target in {"jpg", "bmp", "pdf"}:
        return flatten(image)
    if target == "ico":
        result = image.convert("RGBA")
        result.thumbnail((256, 256), Image.Resampling.LANCZOS)
        return result
    if target == "png" and compress:
        return image.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    return image.copy()


def run(op, items, context):
    if op.id == "image.merge.pdf":
        return merge_pdf(items, context)
    item = items[0]
    name = op.id.removeprefix("image.")
    target = op.target_format or item.format
    quality = context.settings.compress_quality if name == "compress" else context.settings.jpeg_quality
    with load(item.path, context) as source:
        image = source.copy() if op.target_format else edit(source, name)
        with image:
            strip = name in {"strip", "compress"}
            if strip:
                image.info.clear()
            output = context.produce(item, target, lambda path: save(image, path, target, quality, name == "compress", strip), SUFFIXES.get(name, ""))
    if name == "compress":
        context.result.notes.append(f"Size: {item.path.stat().st_size} → {output.stat().st_size} bytes")
    return [output]


def merge_pdf(items, context):
    images = []
    try:
        for item in sorted_items(items):
            context.token.check()
            with load(item.path, context) as image:
                images.append(flatten(image))
        output = context.produce(items[0], "pdf", lambda path: images[0].save(path, "PDF", save_all=True, append_images=images[1:], quality=context.settings.jpeg_quality))
        return [output]
    finally:
        for image in images:
            image.close()
