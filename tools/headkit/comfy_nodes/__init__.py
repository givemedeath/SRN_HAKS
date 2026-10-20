"""ComfyUI adapter entry point; ordinary toolkit/test discovery needs no GPU stack."""
try:
    import folder_paths
except ModuleNotFoundError as exc:
    if exc.name != 'folder_paths':
        raise
    NODE_CLASS_MAPPINGS = {}
else:
    from .nodes import NODE_CLASS_MAPPINGS
