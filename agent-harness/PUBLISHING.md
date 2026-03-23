# PyPI 發佈指南

## 準備工作

### 1. 建立 PyPI 帳號

1. 前往 [PyPI](https://pypi.org/) 註冊帳號
2. 前往 [Test PyPI](https://test.pypi.org/) 註冊測試帳號
3. 設定 API token (建議使用 token 而非密碼)

### 2. 設定認證

建立 `~/.pypirc` 檔案：

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-api-token-here
```

## 發佈流程

### 1. 更新版本號

編輯 `setup.py` 中的 `version`：

```python
setup(
    name="cli-anything-clivoice",
    version="1.0.0",  # 更新版本號
    # ...
)
```

### 2. 建立發佈前檢查清單

```bash
# 1. 執行所有測試
python -m pytest cli_anything/clivoice/tests/ -v

# 2. 檢查程式碼品質
ruff check cli_anything/clivoice/
black --check cli_anything/clivoice/

# 3. 檢查 README 格式
python -m twine check dist/*

# 4. 檢查套件相依性
pipdeptree --packages cli_anything_clivoice
```

### 3. 建立發佈版本

```bash
# 清理舊版本
rm -rf dist/ build/ *.egg-info/

# 建立新版本
python -m build

# 檢查套件
python -m twine check dist/*
```

### 4. 發佈到 Test PyPI (測試)

```bash
# 發佈到測試伺服器
python -m twine upload --repository testpypi dist/*

# 從測試伺服器安裝測試
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple cli-anything-clivoice==1.0.0
```

### 5. 發佈到正式 PyPI

```bash
# 發佈到正式伺服器
python -m twine upload dist/*

# 驗證安裝
pip install cli-anything-clivoice==1.0.0
clivoice --version
```

## 版本控制策略

### 語意化版本 (SemVer)

- **主版本號 (MAJOR)**: 不相容的 API 變更
- **次版本號 (MINOR)**: 向下相容的功能新增  
- **修訂號 (PATCH)**: 向下相容的問題修正

### 發佈標籤

```bash
# 建立 Git 標籤
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 建立 GitHub Release
gh release create v1.0.0 dist/* --title "v1.0.0" --notes "Initial release"
```

## 自動化發佈

### GitHub Actions 工作流程

建立 `.github/workflows/publish.yml`：

```yaml
name: Publish Python Package

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

## 常見問題

### 1. 發佈失敗：套件名稱已存在

```bash
# 檢查套件名稱是否可用
curl https://pypi.org/pypi/cli-anything-clivoice/json
```

如果名稱已被使用，需要修改 `setup.py` 中的 `name`。

### 2. 發佈失敗：版本號已存在

```bash
# 檢查版本號是否已發佈
curl https://pypi.org/pypi/cli-anything-clivoice/1.0.0/json
```

如果版本已存在，需要更新版本號。

### 3. 發佈失敗：相依性問題

```bash
# 檢查相依性
pip install -e . --dry-run
```

確保所有相依性都正確列在 `setup.py` 的 `install_requires` 中。

### 4. 發佈失敗：README 格式錯誤

```bash
# 檢查 README 格式
python -m twine check dist/*
```

確保 README.md 使用正確的 Markdown 格式。

## 維護指南

### 更新相依性

```bash
# 檢查過時套件
pip list --outdated

# 更新相依性
pip install --upgrade package-name

# 更新 requirements.txt
pip freeze > requirements.txt
```

### 文件更新

發佈新版本時，更新：
1. `CHANGELOG.md` - 變更記錄
2. `README.md` - 使用說明
3. `setup.py` - 版本號和相依性

### 支援政策

- 主版本號：支援 2 年
- 次版本號：支援 1 年  
- 修訂號：支援 6 個月

## 聯絡方式

- PyPI 專案頁面：https://pypi.org/project/cli-anything-clivoice/
- GitHub 專案：https://github.com/yourusername/clivoice-cli-harness
- 問題回報：GitHub Issues
