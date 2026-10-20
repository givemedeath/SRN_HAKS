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
    from aiohttp import web
    from server import PromptServer

    import nodes as comfy_core_nodes
    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))

    @PromptServer.instance.routes.post('/headkit/verify-loader-models')
    async def verify_headkit_loader_models(request):
        try:
            payload = await request.json()
            result = verify_loader_models(payload.get('models'), folder_paths, payload.get('prompt'))
        except (KeyError, OSError, TypeError, ValueError):
            return web.json_response({'verified': False}, status=409)
        return web.json_response(result)
