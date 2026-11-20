# Sky panorama sources

`profiles.PANORAMAS` names every picture a build reads; each has its prompt beside it.

- `denver/`: `view_w.png` (Codex CLI image generation from the user's concept, `view_w.prompt.txt`), four extensions
  `ext_<n>.png` and the closing join `join_close.png`, each redrawn by the local Qwen-Image 2.1 profile from its
  `.qwen-prompt.txt` (`panorama.chain`). Green key.
- `peaks/`: three views `view_<x>.png` and the joins between them `join_<xy>.png` (`panorama.assemble`), Qwen edits;
  the Codex prompts of a painted set are kept as `view_<x>.codex-prompt.txt`. Magenta key.
- `<set>/detail/`: the detail pass (`python -m tools.skykit.detail den|pk`), tiles `tile_NN.png` and `detail.json`
  naming the input they were drawn from, from `<set>/detail.qwen-prompt.txt`.
- `join.qwen-prompt.txt`: the generic join prompt; `denver/join_close.qwen-prompt.txt` is a copy of it.
