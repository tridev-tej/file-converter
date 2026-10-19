import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def media(ffmpeg, output, inputs, extra):
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-y", *inputs, "-t", "1.4", *extra, str(output)]
    subprocess.run(command, check=True, capture_output=True)


def text_pdf(path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    for number in range(1, 3):
        page = writer.add_blank_page(width=240, height=180)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 20 Tf 20 90 Td (FileConverter page {number}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def generate(root):
    import zipfile
    import imageio_ffmpeg
    import pillow_heif
    from openpyxl import Workbook
    pillow_heif.register_heif_opener()
    image = Image.new("RGB", (96, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 47, 31), fill="red")
    draw.rectangle((48, 32, 95, 63), fill="blue")
    for name in ("one.png", "two.jpg", "photo.heic", "photo.avif", "multi.tiff"):
        image.save(root / name)
    image.save(root / "animation.gif", save_all=True, append_images=[image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)], duration=200, loop=0)
    Image.new("RGBA", (40, 60), (255, 0, 0, 0)).save(root / "alpha.png")
    text_pdf(root / "one.pdf")
    text_pdf(root / "two.pdf")
    image.save(root / "scan.pdf")
    (root / "notes.md").write_text("# FileConverter document\n\nKnown Unicode café text.\n\n![grid](one.png)\n", encoding="utf-8")
    (root / "notes.txt").write_text("FileConverter plain document", encoding="utf-8")
    book = Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["ID", "Value", "Name"])
    sheet.append(["00123", 42, "café"])
    book.create_sheet("Second").append(["Other", True])
    book.save(root / "book.xlsx")
    (root / "data.csv").write_text('ID,Value,Name\n00123,42,"café, tea"\n', encoding="utf-8-sig")
    (root / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:00,500\n<b>Hello</b>\nworld\n\n2\n00:00:00,500 --> 00:00:01,200\nAgain\n", encoding="utf-8-sig")
    (root / "captions.vtt").write_text("WEBVTT\n\nNOTE metadata\nignore me\n\n00:00.000 --> 00:00.500 align:start\n<b>Hello</b>\nworld\n\n00:00.500 --> 00:01.200\nAgain\n", encoding="utf-8")
    with zipfile.ZipFile(root / "sample.zip", "w") as archive:
        archive.writestr("nested/text.txt", "archive contents café")
        archive.writestr("empty/", "")
    (root / "folder").mkdir()
    (root / "folder" / "file.txt").write_text("copied bytes", encoding="utf-8")
    (root / "destination").mkdir()
    ocr = Image.new("RGB", (1400, 240), "white")
    ImageDraw.Draw(ocr).text((40, 60), "FILE CONVERTER TEST 123", fill="black", font=ImageFont.load_default(size=72))
    ocr.save(root / "ocr.png")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    media(ffmpeg, root / "clip.mp4", ["-f", "lavfi", "-i", "testsrc=size=96x64:rate=12", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"], ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"])
    media(ffmpeg, root / "silent.mp4", ["-f", "lavfi", "-i", "testsrc=size=96x64:rate=12"], ["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    for name, rate, frequency in [("one.wav", 44100, 440), ("two.wav", 48000, 880)]:
        media(ffmpeg, root / name, ["-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate={rate}"], [])
    media(ffmpeg, root / "one.mp3", ["-f", "lavfi", "-i", "sine=frequency=440"], ["-c:a", "libmp3lame"])
    return root
