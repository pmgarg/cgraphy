from dataclasses import dataclass, field


@dataclass
class Sym:
    kind: str              # class | function | method | variable
    name: str
    qualified_name: str
    line_start: int        # 1-based
    line_end: int
    signature: str = ""


@dataclass
class Ref:
    kind: str              # calls | imports | inherits
    source_qname: str      # qualified name of enclosing symbol (or file qname)
    target_name: str


@dataclass
class Extraction:
    syms: list[Sym] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)
    parse_error: bool = False
