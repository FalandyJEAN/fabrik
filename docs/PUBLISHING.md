# Publier Fabrik sur PyPI

Guide pas a pas pour publier une nouvelle version de `fabrik-cli` sur PyPI.

**Pre-requis :**
- Un compte sur https://pypi.org (et idealement sur https://test.pypi.org)
- Un token API PyPI (voir : Account settings -> API tokens)

---

## 1. Premiere fois : preparer l'environnement

```bash
# Cloner et entrer dans le repo
git clone https://github.com/FalandyJEAN/fabrik.git
cd fabrik

# Installer en mode editable avec les outils de build
pip install -e ".[dev]"
```

`[dev]` installe `build` (pour construire le package) et `twine` (pour l'uploader).

---

## 2. Verifier que tout passe

```bash
# Doit dire "RESULTAT : N/N etapes OK"
fabrik test-self
```

Si ca echoue, corrige avant de releaser.

---

## 3. Bumper la version

Dans **2 endroits** (a garder synchronises) :

1. `pyproject.toml` :
   ```toml
   [project]
   version = "1.1.0"   # bump ici
   ```

2. `fabrik/__init__.py` :
   ```python
   __version__ = "1.1.0"   # et ici
   ```

Si c'est un **breaking change** sur la structure des projets generes :
3. `fabrik/scaffold.py` -> `SCAFFOLD_VERSION = N` (bump aussi)
4. Ajouter un `patch_v(N-1)_to_vN(root)` dans `PATCHES`

---

## 4. Build des artefacts

```bash
# Nettoyer les builds precedents
rm -rf dist/ build/ *.egg-info/

# Construire sdist (.tar.gz) et wheel (.whl)
python -m build
```

Tu dois obtenir dans `dist/` :
- `fabrik_cli-1.1.0.tar.gz`     (source)
- `fabrik_cli-1.1.0-py3-none-any.whl`  (wheel universelle)

Verifier la metadata :

```bash
twine check dist/*
```

Doit afficher `PASSED` pour les deux fichiers.

---

## 5. Tester sur Test PyPI d'abord (recommande)

```bash
# Upload sur TestPyPI
twine upload --repository testpypi dist/*
```

Tu seras invite a entrer ton token TestPyPI (commence par `pypi-`).

Tester l'install dans un venv jetable :

```bash
python -m venv /tmp/test-fabrik
source /tmp/test-fabrik/bin/activate      # ou Scripts\activate sur Windows
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            fabrik-cli
fabrik --version
fabrik new /tmp/demo-projet --no-input
deactivate && rm -rf /tmp/test-fabrik
```

Si tout marche, passe a la vraie publication.

---

## 6. Publier sur PyPI (production)

```bash
twine upload dist/*
```

Entre ton token PyPI quand demande.

Verification :

```bash
pip install --upgrade fabrik-cli
fabrik --version       # doit afficher la nouvelle version
```

Ta page : https://pypi.org/project/fabrik-cli/

---

## 7. Tag git + GitHub release

```bash
# Tag local
git tag -a v1.1.0 -m "Fabrik v1.1.0"

# Push code + tag
git push origin main
git push origin v1.1.0

# Creer une release GitHub
gh release create v1.1.0 \
   --title "Fabrik v1.1.0" \
   --notes-from-tag
```

Sans `gh` : va sur `Releases` -> `Draft a new release` sur GitHub.

---

## 8. Automatiser : publish via GitHub Actions

Pour publier automatiquement quand tu pushes un tag `v*` :

`.github/workflows/publish.yml` :

```yaml
name: Publish to PyPI

on:
  push:
    tags: ['v*']

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write        # OIDC trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

Avec **Trusted Publishing** (OIDC) configure sur PyPI, pas besoin de token.
Voir : https://docs.pypi.org/trusted-publishers/

---

## Checklist avant chaque release

- [ ] `fabrik test-self` passe localement
- [ ] Version bumpee dans `pyproject.toml` ET `fabrik/__init__.py`
- [ ] `SCAFFOLD_VERSION` bumpe si breaking change + patch ajoute
- [ ] CHANGELOG ou release notes a jour
- [ ] `python -m build` sans erreur
- [ ] `twine check dist/*` -> PASSED
- [ ] Test sur TestPyPI -> install + `fabrik new` OK
- [ ] Upload PyPI prod
- [ ] Tag git + push
- [ ] Release GitHub creee
