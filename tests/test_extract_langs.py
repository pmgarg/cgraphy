from cgraphy.extract import extract_file


def names(ex):
    return {(s.kind, s.qualified_name) for s in ex.syms}


def refs(ex):
    return {(r.kind, r.source_qname, r.target_name) for r in ex.refs}


JS = b"""
import { fmt } from './util.js';
class Animal { speak() { return fmt(1); } }
class Dog extends Animal { speak() { return this.bark(); } }
function top(x) { return helper(x); }
const helper = (x) => x + 1;
"""


def test_javascript():
    ex = extract_file("javascript", JS, "src.app")
    assert ("class", "src.app.Dog") in names(ex)
    assert ("method", "src.app.Animal.speak") in names(ex)
    assert ("function", "src.app.top") in names(ex)
    assert ("function", "src.app.helper") in names(ex)
    assert ("calls", "src.app.top", "helper") in refs(ex)
    assert ("inherits", "src.app.Dog", "Animal") in refs(ex)
    assert ("imports", "src.app", "./util.js") in refs(ex)


TS = b"""
interface Speaker { speak(): string; }
class Dog implements Speaker { speak() { return bark(); } }
function top(x: number): number { return helper(x); }
"""


def test_typescript():
    ex = extract_file("typescript", TS, "src.app")
    assert ("class", "src.app.Speaker") in names(ex)
    assert ("method", "src.app.Dog.speak") in names(ex)
    assert ("calls", "src.app.top", "helper") in refs(ex)


JAVA = b"""
package zoo;
import java.util.List;
public class Animal {
    public String speak() { return helper(); }
}
class Dog extends Animal {
    public String speak() { return bark(); }
}
"""


def test_java():
    ex = extract_file("java", JAVA, "zoo.Animal")
    assert ("class", "zoo.Animal.Animal") in names(ex)
    assert ("method", "zoo.Animal.Dog.speak") in names(ex)
    assert ("calls", "zoo.Animal.Animal.speak", "helper") in refs(ex)
    assert ("inherits", "zoo.Animal.Dog", "Animal") in refs(ex)
    assert ("imports", "zoo.Animal", "java.util.List") in refs(ex)


GO = b"""
package zoo
import "fmt"
type Animal struct{}
func (a *Animal) Speak() string { return helper() }
func Top(x int) int { return helper(x) }
"""


def test_go():
    ex = extract_file("go", GO, "zoo.animal")
    assert ("class", "zoo.animal.Animal") in names(ex)
    assert ("method", "zoo.animal.Speak") in names(ex)
    assert ("function", "zoo.animal.Top") in names(ex)
    assert ("calls", "zoo.animal.Top", "helper") in refs(ex)
    assert ("imports", "zoo.animal", "fmt") in refs(ex)


C = b"""
#include <stdio.h>
struct point { int x; int y; };
int helper(int x) { return x + 1; }
int top(int x) { return helper(x); }
"""


def test_c():
    ex = extract_file("c", C, "src.main")
    assert ("class", "src.main.point") in names(ex)
    assert ("function", "src.main.top") in names(ex)
    assert ("calls", "src.main.top", "helper") in refs(ex)
    assert ("imports", "src.main", "stdio.h") in refs(ex)


CPP = b"""
#include "zoo.h"
class Animal { public: virtual int speak() { return helper(); } };
class Dog : public Animal { public: int speak() { return bark(); } };
int top(int x) { return helper(x); }
"""


def test_cpp():
    ex = extract_file("cpp", CPP, "src.zoo")
    assert ("class", "src.zoo.Dog") in names(ex)
    assert ("method", "src.zoo.Animal.speak") in names(ex)
    assert ("inherits", "src.zoo.Dog", "Animal") in refs(ex)
    assert ("calls", "src.zoo.top", "helper") in refs(ex)


RUST = b"""
use std::fmt;
struct Animal { name: String }
trait Speaker { fn speak(&self) -> String; }
fn top(x: i32) -> i32 { helper(x) }
fn helper(x: i32) -> i32 { x + 1 }
"""


def test_rust():
    ex = extract_file("rust", RUST, "src.zoo")
    assert ("class", "src.zoo.Animal") in names(ex)
    assert ("class", "src.zoo.Speaker") in names(ex)
    assert ("function", "src.zoo.top") in names(ex)
    assert ("calls", "src.zoo.top", "helper") in refs(ex)
    assert ("imports", "src.zoo", "std::fmt") in refs(ex)
