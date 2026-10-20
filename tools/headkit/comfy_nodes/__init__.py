"""ComfyUI adapter entry point; ordinary toolkit/test discovery needs no GPU stack."""
try:
    import folder_paths
except ModuleNotFoundError as exc:
    if exc.name != 'folder_paths':
        raise
    NODE_CLASS_MAPPINGS = {}
else:
    from .nodes import NODE_CLASS_MAPPINGS
    from .model_resolution import verify_loader_models
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post('/headkit/verify-loader-models')
    async def verify_headkit_loader_models(request):
        try:
            payload = await request.json()
            result = verify_loader_models(payload.get('models'), folder_paths)
        except (KeyError, OSError, TypeError, ValueError):
            return web.json_response({'verified': False}, status=409)
        return web.json_response(result)
