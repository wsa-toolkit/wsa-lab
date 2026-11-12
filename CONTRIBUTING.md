# Contributing to wsa-lab

## Reporting issues

Open an issue on GitHub. Include:

- Protocol number you attempted
- Adapter model and driver
- Output of `iw dev` before starting
- Client device (OS, model) used to test
- For enterprise modes: relevant excerpt from `/tmp/freeradius.log`

## Testing new adapters

If you verify wsa-lab on a new adapter, add a row to the "Tested
hardware" section in `CHANGELOG.md` and open a PR. Include:

- Adapter name and chipset
- Kernel version
- Which protocols you tested

## Pull requests

- One feature per PR
- Keep the code style consistent with the existing file
- Test at least Open + WPA2-Personal before submitting
- Mention any tested protocols in the PR description

## License

By contributing, you agree your changes are released under
GPL-2.0-or-later.
