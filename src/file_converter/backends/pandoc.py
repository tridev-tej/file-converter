"""Pandoc-first document routes with owned resource publication."""

from pathlib import Path

from ..core.formats import file_item
from ..core.output_paths import remove_owned
from ..core.processes import run_process
from ..core.tools import document_route

READERS = dict(md="markdown", txt="markdown", html="html", docx="docx", odt="odt", epub="epub", rtf="rtf")
WRITERS = dict(md="gfm", txt="plain", html="html5", docx="docx", odt="odt", epub="epub3", rtf="rtf")


def convert_file(source, source_format, output, target, context, media=None):
    if source_format not in READERS or target not in WRITERS:
        raise ValueError(f"Unsupported Pandoc conversion: {source_format} → {target}")
    args = [context.tools.pandoc.path, "--from", READERS[source_format], "--to", WRITERS[target], "--standalone", "--resource-path", str(Path(source).parent), "--metadata", "title=" + Path(source).stem, "--output", output]
    if target == "txt":
        args += ["--wrap=none"]
    if media:
        args += ["--extract-media", media]
    args += [source]
    run_process(args, context.token, cwd=Path(source).parent)
    if not Path(output).is_file() or not Path(output).stat().st_size:
        raise RuntimeError("Pandoc exited without its expected non-empty output")


def markdown_export(item, context, source=None):
    source = source or item
    media = context.publisher.stage(item.path.parent, directory=True)
    output = context.publisher.stage(item.path.parent, "md")
    convert_file(source.path, source.format, output, "md", context, media)
    if not list(media.iterdir()):
        return [context.publisher.publish(output, item.path.parent, item.basename, "md", context.token)]
    published = context.publisher.publish(media, item.path.parent, item.basename + " - media", "", context.token)
    try:
        text = output.read_text(encoding="utf-8")
        text = text.replace(str(media), published.name).replace(media.as_uri(), published.name)
        output.write_text(text, encoding="utf-8")
        path = context.publisher.publish(output, item.path.parent, item.basename, "md", context.token)
        return [path, published]
    except Exception:
        try:
            remove_owned(published)
        except OSError as error:
            context.result.notes.append(f"Media cleanup failed for {published}: {error}")
        raise


def run(op, items, context):
    from .office import convert_temp, convert_to_output
    item = items[0]
    target = op.target_format
    route = document_route(item.format, target)
    if route == "office":
        return convert_to_output(item, target, context)
    if route == "pandoc-office":
        intermediate = context.workspace / (item.basename + ".docx")
        convert_file(item.path, item.format, intermediate, "docx", context)
        temporary = file_item(intermediate)
        converted = convert_temp(temporary, "pdf", context)
        return [context.produce(item, "pdf", lambda path: path.write_bytes(converted.read_bytes()))]
    if route == "office-pandoc":
        intermediate = convert_temp(item, "docx", context)
        item_source = file_item(intermediate)
        return pandoc_output(item, item_source, target, context)
    return pandoc_output(item, item, target, context)


def pandoc_output(original, source, target, context):
    if target == "md" and source.format in {"docx", "odt", "epub", "rtf"}:
        return markdown_export(original, context, source)
    return [context.produce(original, target, lambda path: convert_file(source.path, source.format, path, target, context))]
