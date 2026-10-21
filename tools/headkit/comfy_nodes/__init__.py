"""ComfyUI adapter entry point; ordinary toolkit/test discovery needs no GPU stack."""

try:
    import folder_paths
except ModuleNotFoundError as exc:
    if exc.name != 'folder_paths':
        raise
    NODE_CLASS_MAPPINGS = dict()
else:
    from . import nodes as headkit_nodes
    NODE_CLASS_MAPPINGS = headkit_nodes.NODE_CLASS_MAPPINGS
    from .verified_loaders import verified_loader_mappings
    from .model_resolution import verify_loader_models
    from .runtime_identity import capture_runtime_identity
    from .managed_startup import session_context
    from aiohttp import web
    from server import PromptServer

    import nodes as comfy_core_nodes
    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))
    def _capture_startup():
        try:
            session,config=session_context(folder_paths.base_path)
            inventory=config['inventory']
            identity=capture_runtime_identity(folder_paths,inventory,session)
            declared={(row['path'],row['sha256']) for row in config['runtime']['files']}
            if any((row['path'],row['sha256']) not in declared for row in identity['files']):
                raise ValueError('Executing runtime contains files outside the frozen deployment')
            return inventory,session,identity
        except (KeyError, OSError, SyntaxError, TypeError, ValueError):
            return None,None,None

    (_STARTUP_COMFY_SOURCE_INVENTORY,
     _STARTUP_SESSION,
     _STARTUP_RUNTIME_IDENTITY)=_capture_startup()

    @PromptServer.instance.routes.get('/headkit/runtime-identity')
    async def verify_headkit_runtime_identity(request):
        try:
            if _STARTUP_RUNTIME_IDENTITY is None:
                raise ValueError('Comfy server runtime and source baseline could not be captured at adapter load; use the controlled startup wrapper in a new instance when available')
            session,config=session_context(folder_paths.base_path)
            if session != _STARTUP_SESSION:
                raise ValueError('Controlled Comfy session changed; prepare again')
        except (KeyError, OSError, SyntaxError, TypeError, ValueError):
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
