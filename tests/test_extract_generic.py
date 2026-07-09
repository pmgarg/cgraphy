from cgraphy.extract import extract_file

RUBY = b"""
class Animal
  def speak
    'hi'
  end
end
def top(x)
  x + 1
end
"""


def test_ruby_defs_via_generic_fallback():
    ex = extract_file("ruby", RUBY, "app.zoo")
    got = {(s.kind, s.qualified_name) for s in ex.syms}
    assert ("class", "app.zoo.Animal") in got
    assert ("method", "app.zoo.Animal.speak") in got
    assert ("function", "app.zoo.top") in got


def test_unknown_language_returns_empty_not_error():
    ex = extract_file(None, b"key: value\n", "config")
    assert ex.syms == [] and not ex.parse_error
