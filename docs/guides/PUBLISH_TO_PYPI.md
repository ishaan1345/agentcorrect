# Publishing AgentCorrect to PyPI

## Prerequisites

1. Create a PyPI account at https://pypi.org/account/register/
2. Create an API token at https://pypi.org/manage/account/token/
3. Install build tools:
```bash
pip install --upgrade pip build twine
```

## Step 1: Test on TestPyPI First (Recommended)

### 1.1 Create TestPyPI account
- Register at https://test.pypi.org/account/register/
- Create API token at https://test.pypi.org/manage/account/token/

### 1.2 Build the package
```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build source and wheel distributions
python -m build
```

### 1.3 Upload to TestPyPI
```bash
python -m twine upload --repository testpypi dist/*
# Username: __token__
# Password: <your-test-pypi-token>
```

### 1.4 Test installation from TestPyPI
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ agentcorrect
```

### 1.5 Verify it works
```bash
# Test the CLI
agentcorrect --version

# Test with a sample trace
echo '{"role":"sql","meta":{"sql":{"query":"DELETE FROM users WHERE 1=1"}}}' | agentcorrect analyze -
```

## Step 2: Publish to Production PyPI

### 2.1 Final checks
- [ ] All tests pass: `python3 ship_tests.py`
- [ ] Version updated in `agentcorrect/__init__.py`
- [ ] README.md is complete and renders correctly
- [ ] LICENSE file exists
- [ ] Dependencies listed in setup.py and requirements.txt

### 2.2 Build final package
```bash
# Clean and rebuild
rm -rf dist/ build/ *.egg-info/
python -m build
```

### 2.3 Upload to PyPI
```bash
python -m twine upload dist/*
# Username: __token__
# Password: <your-pypi-token>
```

### 2.4 Verify installation
```bash
# In a new virtual environment
pip install agentcorrect
agentcorrect --version
```

## Step 3: Post-Publication

### 3.1 Test public installation
```bash
# Create fresh environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from PyPI
pip install agentcorrect

# Run verification
./quick_proof.sh  # or quick_proof.ps1 on Windows
```

### 3.2 Update GitHub
```bash
# Tag the release
git tag -a v0.1.0 -m "Initial PyPI release"
git push origin v0.1.0

# Create GitHub release
gh release create v0.1.0 --title "v0.1.0 - PyPI Release" --notes "Now available: pip install agentcorrect"
```

### 3.3 Announce
- Update README with: `pip install agentcorrect`
- Post on HackerNews/Reddit/Twitter
- Update documentation site

## Automation with GitHub Actions

Create `.github/workflows/publish.yml`:
```yaml
name: Publish to PyPI
on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: |
        python -m twine upload dist/*
```

## Troubleshooting

### Package name already taken
- Try: `agentcorrect-ai`, `agentcorrect-cicd`, or `ai-agentcorrect`

### Description too long
- Shorten README.md or use a separate PYPI_README.md

### Missing dependencies error
- Ensure sqlparse and tldextract are in install_requires

### Import errors after installation
- Check MANIFEST.in includes all necessary files
- Verify package structure with: `tar -tzf dist/*.tar.gz`

## Security Notes

1. **Never commit tokens**: Store PyPI tokens as environment variables or in ~/.pypirc
2. **Use API tokens**: Not username/password
3. **Test on TestPyPI first**: Always test before production release
4. **Verify package contents**: Check no sensitive files are included

## Quick Release Checklist

```bash
# 1. Update version
sed -i 's/__version__ = ".*"/__version__ = "0.1.0"/' agentcorrect/__init__.py

# 2. Run tests
python3 verify.py
python3 ship_tests.py

# 3. Build
rm -rf dist/ build/
python -m build

# 4. Upload
python -m twine upload dist/*

# 5. Verify
pip install --upgrade agentcorrect
agentcorrect --version
```

Once published, anyone can install with:
```bash
pip install agentcorrect
```