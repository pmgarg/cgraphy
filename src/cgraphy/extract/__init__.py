from cgraphy.extract.base import Extraction
from cgraphy.extract.engine import extract_tier1
from cgraphy.extract.langs import TIER1


def extract_file(lang, source: bytes, module_qname: str) -> Extraction:
    try:
        if lang in TIER1:
            return extract_tier1(lang, source, module_qname)
        return Extraction()  # replaced by generic fallback in Task 7
    except Exception:
        return Extraction(parse_error=True)
