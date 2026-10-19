"""English Vision OCR; clipboard publication belongs to the UI thread."""

import sys


def recognize(path):
    if sys.platform != "darwin":
        raise RuntimeError("OCR is not available on Windows in v1.")
    import Vision
    from Foundation import NSURL, NSAutoreleasePool
    pool = NSAutoreleasePool.alloc().init()
    try:
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["en-US"])
        request.setUsesLanguageCorrection_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(path)), {})
        success, error = handler.performRequests_error_([request], None)
        if not success:
            detail = str(error) if error is not None else "Vision returned false without NSError; native OCR service may be unavailable in this process environment"
            raise RuntimeError(f"Vision OCR failed: {detail}")
        lines = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                lines.append(str(candidates[0].string()))
        return "\n".join(lines)
    finally:
        del pool


def image_text(item, context):
    from .image import load
    path = context.workspace / "ocr-image.png"
    with load(item.path, context) as image:
        image.convert("RGB").save(path, "PNG")
    return recognize(path)


def pdf_text(item, context):
    from .pdf import document, render_page
    texts = []
    with document(item.path) as pdf:
        for index in range(len(pdf)):
            context.token.check()
            path = context.workspace / f"ocr-{index}.png"
            with render_page(pdf, index, context.settings.pdf_dpi) as image:
                image.save(path, "PNG")
            texts.append(recognize(path))
    return "\n\n".join(texts)


def run(op, items, context):
    item = items[0]
    text = pdf_text(item, context) if item.format == "pdf" else image_text(item, context)
    if not text.strip():
        raise ValueError("OCR did not recognize any English text")
    output = context.produce(item, "txt", lambda path: path.write_text(text + "\n", encoding="utf-8"), "text")
    previous = context.result.clipboard_text
    context.result.clipboard_text = previous + "\n\n" + text if previous else text
    return [output]
