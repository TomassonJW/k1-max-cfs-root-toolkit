"""Le gestionnaire de bobines tourne sous le Python 3.8.2 du Moonraker K1 Control.

Document 102. Le poste et la CI ont un Python plus récent : chaque module est
lu avec la grammaire 3.8, et ce qui n'est apparu qu'après 3.8 est refusé
(méthodes, modules, noms de typing, `list[...]`, `zip(strict=)`,
`isinstance(x, A | B)`, `dict | dict`). Le cœur (stockage, modèle, décompte)
n'importe que la bibliothèque standard, aucun module voisin et aucun
transport ; l'adaptateur Moonraker n'importe que le cœur et le socle
Moonraker. Le préflight du lot K compile et importe encore les sources sur la
vraie K1, par stdin et sans fichier distant.
"""

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "spool-manager-v1"
CORE = {"kctrl_spools_store", "kctrl_spools_model", "kctrl_spools_counter"}
ADAPTER = "kctrl_spools"
TOOLS = {"build_tares"}  # Run on the workstation only.
SOURCES = sorted(PACKAGE.glob("*.py"))
TRANSPORT = {"asyncio", "ctypes", "ftplib", "http", "multiprocessing", "select", "selectors", "smtplib",
             "socket", "socketserver", "ssl", "subprocess", "telnetlib", "urllib", "xmlrpc"}
MOONRAKER = {"common", "confighelper"}

# What appeared after 3.8, by module and name, by method name and by builtin.
NEWER_MODULES = {"graphlib", "tomllib", "zoneinfo"}
NEWER_NAMES = {
    ("asyncio", "TaskGroup"), ("asyncio", "timeout"), ("asyncio", "to_thread"),
    ("contextlib", "aclosing"), ("contextlib", "chdir"), ("datetime", "UTC"),
    ("functools", "cache"), ("hashlib", "file_digest"), ("itertools", "pairwise"),
    ("math", "lcm"), ("math", "nextafter"), ("math", "ulp"), ("random", "randbytes"),
} | {("typing", name) for name in (
    "Annotated", "Concatenate", "LiteralString", "Never", "NotRequired", "ParamSpec", "Required", "Self",
    "TypeAlias", "TypeGuard", "TypeVarTuple", "Unpack", "assert_never", "assert_type",
    "dataclass_transform", "is_typeddict", "override", "reveal_type")}
NEWER_METHODS = {"bit_count", "is_relative_to", "removeprefix", "removesuffix", "with_stem"}
NEWER_BUILTINS = {"BaseExceptionGroup", "EncodingWarning", "ExceptionGroup", "aiter", "anext"}
BUILTIN_GENERICS = {"dict", "frozenset", "list", "set", "tuple", "type"}
NEWER_KEYWORDS = {"zip": {"strict"}, "dataclass": {"kw_only", "slots"}, "field": {"kw_only"},
                  "bisect": {"key"}, "bisect_left": {"key"}, "bisect_right": {"key"},
                  "insort": {"key"}, "insort_left": {"key"}, "insort_right": {"key"}}


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.name, feature_version=(3, 8))


def called(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def is_dict(node):
    return isinstance(node, (ast.Dict, ast.DictComp)) or (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict")


def newer(tree):
    found = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Attribute):
            if node.attr in NEWER_METHODS:
                found.append("%d: .%s" % (line, node.attr))
            if isinstance(node.value, ast.Name) and (node.value.id, node.attr) in NEWER_NAMES:
                found.append("%d: %s.%s" % (line, node.value.id, node.attr))
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in NEWER_MODULES:
                found.append("%d: %s" % (line, node.module))
            found.extend("%d: %s.%s" % (line, node.module, alias.name)
                         for alias in node.names if (node.module, alias.name) in NEWER_NAMES)
        if isinstance(node, ast.Import):
            found.extend("%d: %s" % (line, alias.name)
                         for alias in node.names if alias.name.split(".")[0] in NEWER_MODULES)
        if isinstance(node, ast.Name) and node.id in NEWER_BUILTINS:
            found.append("%d: %s" % (line, node.id))
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and node.value.id in BUILTIN_GENERICS:
            found.append("%d: %s[...]" % (line, node.value.id))
        if isinstance(node, ast.Call):
            name = called(node)
            found.extend("%d: %s(%s=)" % (line, name, keyword.arg) for keyword in node.keywords
                         if keyword.arg in NEWER_KEYWORDS.get(name, ()))
            if name in ("isinstance", "issubclass") and len(node.args) == 2 \
                    and isinstance(node.args[1], ast.BinOp) and isinstance(node.args[1].op, ast.BitOr):
                found.append("%d: %s(x, A | B)" % (line, name))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) \
                and (is_dict(node.left) or is_dict(node.right)):
            found.append("%d: dict | dict" % line)
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.BitOr) and is_dict(node.value):
            found.append("%d: |= dict" % line)
    return found


def imports(tree):
    """(level, module, names) for every import, nested ones included."""
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend((0, alias.name, ()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.append((node.level, node.module or "", tuple(alias.name for alias in node.names)))
    return result


def test_every_module_of_the_package_is_classified():
    stems = {path.stem for path in SOURCES}
    assert stems - TOOLS == CORE | {ADAPTER}, (stems - TOOLS) ^ (CORE | {ADAPTER})
    assert {"kctrl_spools_store", "kctrl_spools_model"} <= stems


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: path.name)
def test_the_module_parses_as_python_3_8_and_uses_nothing_newer(path):
    assert newer(parse(path)) == []


def test_the_detector_sees_what_3_8_lacks():
    source = "\n".join([
        "import zoneinfo", "from typing import TypeAlias", "from functools import cache",
        "x = 'a'.removeprefix('b')", "y: list[int] = []", "z = list[int]", "zip(a, b, strict=True)",
        "isinstance(v, int | str)", "d = {} | {}", "d |= dict(a=1)", "asyncio.to_thread(f)",
        "anext(it)", "bisect.insort(a, x, key=len)",
    ])
    found = newer(ast.parse(source, feature_version=(3, 8)))
    assert sorted(found, key=lambda item: int(item.split(":")[0])) == [
        "1: zoneinfo", "2: typing.TypeAlias", "3: functools.cache", "4: .removeprefix", "5: list[...]",
        "6: list[...]", "7: zip(strict=)", "8: isinstance(x, A | B)", "9: dict | dict", "10: |= dict",
        "11: asyncio.to_thread", "12: anext", "13: insort(key=)"]
    with pytest.raises(SyntaxError):
        ast.parse("with (open('a') as f, open('b') as g):\n    pass\n", feature_version=(3, 8))
    with pytest.raises(SyntaxError):
        ast.parse("match x:\n    case 1:\n        pass\n", feature_version=(3, 8))


@pytest.mark.parametrize("path", [path for path in SOURCES if path.stem in CORE], ids=lambda path: path.name)
def test_the_core_imports_only_the_standard_library_and_no_transport(path):
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        pytest.skip("sys.stdlib_module_names demande Python 3.10")
    for level, module, names in imports(parse(path)):
        top = module.split(".")[0]
        assert level == 0, "%s : import relatif %s" % (path.name, module or names)
        assert top in stdlib, "%s : %s hors bibliothèque standard" % (path.name, module)
        assert top not in TRANSPORT, "%s : transport %s" % (path.name, module)


def test_the_adapter_imports_only_its_core_and_moonraker():
    path = PACKAGE / (ADAPTER + ".py")
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        pytest.skip("sys.stdlib_module_names demande Python 3.10")
    for level, module, names in imports(parse(path)):
        top = module.split(".")[0]
        if level == 0:
            assert top in stdlib and top not in TRANSPORT - {"asyncio"}, module
        elif level == 1:
            assert (module in CORE) if module else set(names) <= CORE, (module, names)
        else:
            assert level == 2 and module in MOONRAKER, (level, module)
