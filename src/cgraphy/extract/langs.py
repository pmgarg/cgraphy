from dataclasses import dataclass


@dataclass
class LanguageSpec:
    defs_query: str
    refs_query: str


def _py_import(text: str) -> str:
    return text.split(".")[0].strip()


PYTHON = LanguageSpec(
    defs_query="""
(function_definition name: (identifier) @name) @def.function
(class_definition name: (identifier) @name) @def.class
""",
    refs_query="""
(call function: (identifier) @call.name)
(call function: (attribute attribute: (identifier) @call.name))
(import_statement name: (dotted_name) @import.module)
(import_statement name: (aliased_import name: (dotted_name) @import.module))
(import_from_statement module_name: (dotted_name) @import.module)
(class_definition superclasses: (argument_list (identifier) @inherit.name))
""",
)

TIER1: dict[str, LanguageSpec] = {"python": PYTHON}

IMPORT_CLEANERS = {"python": _py_import}
