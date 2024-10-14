## How to install?

### install python3
We recommend using the latest version of Python. `python3` supports Python 3.12+.
```bash
sudo apt update
sudo apt install python3
sudo apt install python3-venv
python3 --version
```

## How to build?
```bash
python3 -m venv venv
source venv/bin/activate
```

### install dependencies
```bash
sudo apt install build-essential python3-dev
pip install web3==6.14.0
pip install openpyxl
```

## How to run?
Run command ``python3 main.py``, from root directory.

"modified_pair.xlsx" file generated on root directory.