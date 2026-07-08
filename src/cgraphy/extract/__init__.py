from cgraphy.extract.base import Extraction
from cgraphy.extract.engine import extract_tier1
from cgraphy.extract.generic import extract_generic
from cgraphy.extract.langs import TIER1


def extract_file(lang, source: bytes, module_qname: str) -> Extraction:
    if lang is None:
        return Extraction()
    try:
        if lang in TIER1:
            return extract_tier1(lang, source, module_qname)
        return extract_generic(lang, source, module_qname)
    except Exception:
        return Extraction(parse_error=True)
