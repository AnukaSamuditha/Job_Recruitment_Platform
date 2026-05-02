from hypothesis import given
from hypothesis import strategies as st

from app.services.text_chunker import chunk_text


@given(st.text())
def test_chunk_text_never_crushes(s: str) -> None:
    out = chunk_text(s)
    assert isinstance(out, list)
    for c in out:
        assert isinstance(c, str)
        assert len(c) <= 900 or len(s) <= 900
