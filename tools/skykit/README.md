# skykit

Dynamic skyboxes for NWN:EE: fixed land panoramas over a procedural, animated sky. See
[docs/skies/dynamic-skies.md](../../docs/skies/dynamic-skies.md).

- `profiles.py`: the panoramas, the `skyboxes.2da` rows and every phase's material parameters. Change looks here.
- `panorama.py`: keyed source views to a 360-degree strip, texture halves and light masks.
- `sphere.py`: the inward-facing dome as an ASCII model.
- `preview.py`: renders the real shader off-screen (ModernGL) for previews and fallback pictures.
- `__main__.py`: `python -m tools.skykit build` writes `srn_skybox`, the table rows and `docs/skies/manifest.json`.
- `detail.py`: the land redrawn in tracked Qwen tiles (`python -m tools.skykit.detail den|pk`), blended by the build.
- `upscale.py`: the 2x RealESRGAN fallback for a panorama without detail tiles; `run_graph` reaches the shared ComfyUI.
- `normals.py`: MoGe-2 normals of the land, for the shader's relighting.
- `client_fixture.py`: an isolated test module and client run with scripted captures (`--transition` lets time run
  through dusk and dawn, `--play` leaves a fast day cycle running for a person, `--live 8` the game's own
  clock at 8 real minutes an hour with chat commands).

The detail, upscale and normals jobs use the GPU shared with other sessions; their results are cached, so a rebuild of
unchanged art needs none.
- `art/`: the source views and their prompts.

Verification: `python -m unittest tools.skykit.test_skykit` (the GL test runs only where ModernGL makes a context).
