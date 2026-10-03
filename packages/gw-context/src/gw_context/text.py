"""Pure text splitting for context candidates, independent of storage/indexing."""
from .contract import integer, text


def chunks(content: str, width: int = 1800):
    """Exact Unicode character ranges, biased toward newline boundaries."""
    text(content, "chunk content", 2_000_000, empty=True)
    integer(width, "chunk width", 1, 2_000_000)
    start, line, ordinal = 0, 1, 0
    while start < len(content):
        end = min(len(content), start + width)
        if end < len(content):
            boundary = content.rfind("\n", start + width // 2, end)
            if boundary >= 0:
                end = boundary + 1
        piece = content[start:end]
        end_line = line + (piece[:-1] if piece.endswith("\n") else piece).count("\n")
        yield ordinal, piece, start, end, line, end_line
        line += piece.count("\n")
        start, ordinal = end, ordinal + 1
    if not content:
        yield 0, "", 0, 0, 1, 1
