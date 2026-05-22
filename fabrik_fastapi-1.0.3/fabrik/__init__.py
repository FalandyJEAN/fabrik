"""
Fabrik -- Generateur de projet FastAPI async + opinionated.

Usage CLI :
    fabrik new mon-api
    fabrik add videos
    fabrik upgrade
    fabrik test-self

Voir : https://github.com/FalandyJEAN/fabrik
"""
__version__ = "1.0.2"
__author__ = "Falandy Jean"
__license__ = "MIT"

from fabrik.scaffold import SCAFFOLD_VERSION, build_files, main

__all__ = ["SCAFFOLD_VERSION", "build_files", "main", "__version__"]
