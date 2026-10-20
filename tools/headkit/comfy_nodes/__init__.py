"""ComfyUI adapter entry point; ordinary toolkit/test discovery needs no GPU stack."""
try:
    import folder_paths
except ModuleNotFoundError as exc:
    if exc.name != 'folder_paths':
        raise
    NODE_CLASS_MAPPINGS = {}
else:
    from .nodes import NODE_CLASS_MAPPINGS
    from .verified_loaders import verified_loader_mappings
    from .model_resolution import verify_loader_models
    from .runtime_identity import capture_runtime_identity
    from aiohttp import web
    from server import PromptServer

    import nodes as comfy_core_nodes
    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))
    try:
        _STARTUP_RUNTIME_IDENTITY = capture_runtime_identity(folder_paths)
    except (OSError, TypeError, ValueError):
        _STARTUP_RUNTIME_IDENTITY = None

    @PromptServer.instance.routes.post('/headkit/runtime-identity')
    async def verify_headkit_runtime_identity(request):
        try:
            if _STARTUP_RUNTIME_IDENTITY is None:
                raise ValueError('Comfy server runtime baseline could not be captured at adapter load')
            current = capture_runtime_identity(folder_paths)
            if current != _STARTUP_RUNTIME_IDENTITY:
                raise ValueError('Comfy server runtime files changed after the adapter loaded')
        except (OSError, TypeError, ValueError):
            return web.json_response({'verified': False}, status=409)
        return web.json_response(_STARTUP_RUNTIME_IDENTITY)

    @PromptServer.instance.routes.post('/headkit/verify-loader-models')
    async def verify_headkit_loader_models(request):
        try:
            payload = await request.json()
            result = verify_loader_models(payload.get('models'), folder_paths, payload.get('prompt'))
        except (KeyError, OSError, TypeError, ValueError):
            return web.json_response({'verified': False}, status=409)
        return web.json_response(result)
