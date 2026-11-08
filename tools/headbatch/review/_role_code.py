"""Transitive source inventory for the saved-ownership numeric preflight."""
import ast
from pathlib import Path
from headkit.common import module_closure, module_path


def files():
    review = Path(__file__).resolve().parent
    directory = review.parents[1]/'headkit'
    checker = review/'roles.py'
    names = set()
    for node in ast.walk(ast.parse(checker.read_text(encoding='utf-8'))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('headkit.'):
            names.add(node.module.removeprefix('headkit.'))
    return sorted({checker, Path(__file__).resolve(), directory/'quality-thresholds.json',
                   *(module_path(name, directory) for name in module_closure(names, directory))})
