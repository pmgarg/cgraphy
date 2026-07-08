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

_JS_DEFS = """
(function_declaration name: (identifier) @name) @def.function
(class_declaration name: (identifier) @name) @def.class
(method_definition name: (property_identifier) @name) @def.function
(variable_declarator name: (identifier) @name value: (arrow_function)) @def.function
"""
_JS_REFS = """
(call_expression function: (identifier) @call.name)
(call_expression function: (member_expression property: (property_identifier) @call.name))
(import_statement source: (string) @import.module)
(class_heritage (identifier) @inherit.name)
"""

JAVASCRIPT = LanguageSpec(defs_query=_JS_DEFS, refs_query=_JS_REFS)

# TypeScript's grammar diverges from JavaScript's: class names are
# type_identifier and heritage is extends_clause/implements_clause.
TYPESCRIPT = LanguageSpec(
    defs_query="""
(function_declaration name: (identifier) @name) @def.function
(class_declaration name: (type_identifier) @name) @def.class
(method_definition name: (property_identifier) @name) @def.function
(variable_declarator name: (identifier) @name value: (arrow_function)) @def.function
(interface_declaration name: (type_identifier) @name) @def.class
(type_alias_declaration name: (type_identifier) @name) @def.class
""",
    refs_query="""
(call_expression function: (identifier) @call.name)
(call_expression function: (member_expression property: (property_identifier) @call.name))
(import_statement source: (string) @import.module)
(extends_clause value: (identifier) @inherit.name)
(implements_clause (type_identifier) @inherit.name)
""",
)

JAVA = LanguageSpec(
    defs_query="""
(class_declaration name: (identifier) @name) @def.class
(interface_declaration name: (identifier) @name) @def.class
(enum_declaration name: (identifier) @name) @def.class
(method_declaration name: (identifier) @name) @def.function
(constructor_declaration name: (identifier) @name) @def.function
""",
    refs_query="""
(method_invocation name: (identifier) @call.name)
(import_declaration (scoped_identifier) @import.module)
(superclass (type_identifier) @inherit.name)
(super_interfaces (type_list (type_identifier) @inherit.name))
""",
)

GO = LanguageSpec(
    defs_query="""
(function_declaration name: (identifier) @name) @def.function
(method_declaration name: (field_identifier) @name) @def.method
(type_declaration (type_spec name: (type_identifier) @name)) @def.class
""",
    refs_query="""
(call_expression function: (identifier) @call.name)
(call_expression function: (selector_expression field: (field_identifier) @call.name))
(import_spec path: (interpreted_string_literal) @import.module)
""",
)

C_SPEC = LanguageSpec(
    defs_query="""
(function_definition declarator: (function_declarator declarator: (identifier) @name)) @def.function
(struct_specifier name: (type_identifier) @name body: (field_declaration_list)) @def.class
(enum_specifier name: (type_identifier) @name body: (enumerator_list)) @def.class
""",
    refs_query="""
(call_expression function: (identifier) @call.name)
(preproc_include path: (system_lib_string) @import.module)
(preproc_include path: (string_literal) @import.module)
""",
)

CPP = LanguageSpec(
    defs_query=C_SPEC.defs_query + """
(class_specifier name: (type_identifier) @name body: (field_declaration_list)) @def.class
(function_definition declarator: (function_declarator declarator: (field_identifier) @name)) @def.function
(function_definition declarator: (function_declarator declarator: (qualified_identifier name: (identifier) @name))) @def.function
""",
    refs_query=C_SPEC.refs_query + """
(call_expression function: (field_expression field: (field_identifier) @call.name))
(base_class_clause (type_identifier) @inherit.name)
""",
)

RUST = LanguageSpec(
    defs_query="""
(function_item name: (identifier) @name) @def.function
(struct_item name: (type_identifier) @name) @def.class
(enum_item name: (type_identifier) @name) @def.class
(trait_item name: (type_identifier) @name) @def.class
""",
    refs_query="""
(call_expression function: (identifier) @call.name)
(call_expression function: (field_expression field: (field_identifier) @call.name))
(use_declaration argument: (_) @import.module)
""",
)

TIER1: dict[str, LanguageSpec] = {
    "python": PYTHON,
    "javascript": JAVASCRIPT, "typescript": TYPESCRIPT, "java": JAVA,
    "go": GO, "c": C_SPEC, "cpp": CPP, "rust": RUST,
}

IMPORT_CLEANERS = {"python": _py_import}
