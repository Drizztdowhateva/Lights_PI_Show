# Contributing

Thanks for your interest in contributing to Lights PI Show.

## How to contribute

1. Fork the repository and create a feature branch.
2. Make focused, testable changes.
3. Update `CHANGELOG.md` and documentation where appropriate.
4. Open a pull request with a clear description of the change.

## Development setup

```bash
git clone https://github.com/Drizztdowhateva/Lights_PI_Show.git
cd Lights_PI_Show
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For GUI work, also install GTK3:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

## Testing without hardware

```bash
# CLI simulation
python3 into.py --test --pattern 1 --frames 30

# GUI simulation
python3 gui.py --test
```

## Pull request checklist

- [ ] Runs without errors in `--test` / `--gui --test` mode
- [ ] New behaviour is documented in `README.md`
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`
- [ ] No hardcoded paths, API keys, or secrets
- [ ] Backward compatibility considered (CLI args, headless JSON format)

## Code conventions

- `into.py` — CLI logic and pattern engine; importable as a module (has `if __name__ == "__main__"` guard)
- `gui.py` — GTK3 GUI; imports from `into`
- `runtimes/runtime_package.py` — packaging only; no LED logic
- Keep new patterns in `run_pattern_step()` and registered in `PATTERN_NAMES`, `PATTERN_CYCLE_ORDER`, and `SPEED_MAP`

## License

By contributing you agree that your changes will be licensed under the [MIT License](LICENSE).
