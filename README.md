# Demystifying The GIL
Pycon 2026 Presentation

With GIL:
```
uv run --python 3.14 unsafe.py
```

Without GIL
```
uv run --python 3.14t unsafe.py
```

NOTE: uv seems to get stuck using 3.14t so the "With GIL" version ends up using 3.14t anyway, when the virtual environment is active. 
One solution is to *not* activate the venv and run:
```
python unsafe.py
```
