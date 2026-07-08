from cgraphy.extract import extract_file

SRC = b'''\
import os
from collections import OrderedDict

def top(x):
    return helper(x)

def helper(x):
    return os.path.join(x, "y")

class Animal:
    def speak(self):
        return top(1)

class Dog(Animal):
    def speak(self):
        return self.bark()
'''


def _ex():
    return extract_file("python", SRC, "pkg.zoo")


def test_symbols_with_kinds_and_qnames():
    ex = _ex()
    got = {(s.kind, s.qualified_name) for s in ex.syms}
    assert ("function", "pkg.zoo.top") in got
    assert ("class", "pkg.zoo.Animal") in got
    assert ("method", "pkg.zoo.Animal.speak") in got
    assert ("method", "pkg.zoo.Dog.speak") in got


def test_calls_attached_to_enclosing_symbol():
    refs = {(r.kind, r.source_qname, r.target_name) for r in _ex().refs}
    assert ("calls", "pkg.zoo.top", "helper") in refs
    assert ("calls", "pkg.zoo.Animal.speak", "top") in refs
    assert ("calls", "pkg.zoo.Dog.speak", "bark") in refs


def test_imports_and_inheritance():
    refs = {(r.kind, r.source_qname, r.target_name) for r in _ex().refs}
    assert ("imports", "pkg.zoo", "os") in refs
    assert ("imports", "pkg.zoo", "collections") in refs
    assert ("inherits", "pkg.zoo.Dog", "Animal") in refs


def test_signature_is_first_line():
    top = next(s for s in _ex().syms if s.qualified_name == "pkg.zoo.top")
    assert top.signature == "def top(x):" and top.line_start == 4
