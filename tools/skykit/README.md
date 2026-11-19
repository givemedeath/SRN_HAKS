# skykit

Dynamic skyboxes for NWN:EE: fixed land panoramas over a procedural, animated sky. See
[docs/skies/dynamic-skies.md](../../docs/skies/dynamic-skies.md).

- `profiles.py`: the panoramas, the `skyboxes.2da` rows and every phase's material parameters. Change looks here.
- `panorama.py`: keyed source views to a 360-degree strip, texture halves and light masks.
- `sphere.py`: the inward-facing dome as an ASCII model.
- `preview.py`: renders the real shader off-screen (ModernGL) for previews and fallback pictures.
- `__main__.py`: `python -m tools.skykit build` writes `srn_skybox`, the table rows and `docs/skies/manifest.json`.
- `client_fixture.py`: an isolated test module and client run with scripted captures (`--transition` lets time run
  through dusk and dawn).
- `art/`: the source views and their prompts.

Verification: `python -m unittest tools.skykit.test_skykit` (the GL test runs only where ModernGL makes a context).
