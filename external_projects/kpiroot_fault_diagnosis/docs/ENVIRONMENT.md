# FinalProject Environment

## Python

Activate the project-local Conda environment:

```powershell
conda activate D:\Study\SoftwareTesting\FinalProject\.conda
```

Verify the environment:

```powershell
python -c "import numpy,pandas,scipy,sklearn,statsmodels,matplotlib; print('env ok')"
```

Install or refresh dependencies:

```powershell
python -m pip install -r requirements.txt
```

## GitHub CLI

GitHub CLI is installed for the current user at:

```text
C:\Users\Sinclair\bin\gh.exe
```

Verify:

```powershell
gh --version
```

Log in when you are ready to push or create repositories:

```powershell
gh auth login
```
