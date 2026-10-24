"""ComfyUI adapter entry point; ordinary toolkit/test discovery needs no GPU stack."""
from pathlib import Path
import logging
import json

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
    from .runtime_identity import capture_runtime_identity,same_runtime_environment
    from .source_snapshot import capture_inventory,load_inventory,loaded_source_code,same_inventory
    from .verification import HEAVY_VERIFICATION_LOCK,verification_pass
    from aiohttp import web
    from server import PromptServer

    import nodes as comfy_core_nodes
    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))
    def _capture_startup():
        try:
            with HEAVY_VERIFICATION_LOCK,verification_pass('server-startup') as session:
                with session.phase('source-inventory'):
                    inventory=load_inventory(Path(__file__).parent/'source-roots.json',folder_paths.base_path)
                with session.phase('loaded-code'):
                    loaded=loaded_source_code(inventory['roots'])
                with session.phase('runtime-files'):
                    identity=capture_runtime_identity(folder_paths,inventory,loaded)
            return inventory,loaded,identity
        except (OSError, SyntaxError, TypeError, ValueError):
            logging.getLogger(__name__).exception('Headkit runtime baseline capture failed; dispatch remains blocked')
            return None,None,None

    (_STARTUP_COMFY_SOURCE_INVENTORY,
     _STARTUP_LOADED_SOURCE_CODE,
     _STARTUP_RUNTIME_IDENTITY)=_capture_startup()

    @PromptServer.instance.routes.get('/headkit/runtime-identity')
    async def verify_headkit_runtime_identity(request):
        try:
            if _STARTUP_RUNTIME_IDENTITY is None:
                raise ValueError('Comfy server runtime and source baseline could not be captured at adapter load; reinstall the adapter with local bindings and restart ComfyUI')
            with HEAVY_VERIFICATION_LOCK,verification_pass('server-request') as session:
                with session.phase('source-inventory'):
                    current_sources=capture_inventory(_STARTUP_COMFY_SOURCE_INVENTORY['core'],
                                                     _STARTUP_COMFY_SOURCE_INVENTORY['roots'])
                    if not same_inventory(current_sources,_STARTUP_COMFY_SOURCE_INVENTORY):
                        raise ValueError('Comfy source files changed after the adapter loaded')
                with session.phase('loaded-code'):
                    loaded=loaded_source_code(_STARTUP_COMFY_SOURCE_INVENTORY['roots'])
                with session.phase('runtime-files'):
                    current = capture_runtime_identity(folder_paths,_STARTUP_COMFY_SOURCE_INVENTORY,loaded)
                    if not same_runtime_environment(current,_STARTUP_RUNTIME_IDENTITY):
                        raise ValueError('Comfy server runtime files changed after the adapter loaded')
        except (OSError, SyntaxError, TypeError, ValueError):
            logging.getLogger(__name__).exception('Headkit live runtime verification failed; dispatch remains blocked')
            return web.json_response({'verified': False}, status=409)
        return web.json_response(current,headers={'X-Headkit-Verification':json.dumps(session.report(),separators=(',',':'))})

    @PromptServer.instance.routes.post('/headkit/verify-loader-models')
    async def verify_headkit_loader_models(request):
        try:
            payload = await request.json()
            with HEAVY_VERIFICATION_LOCK,verification_pass('server-models') as session:
                result = verify_loader_models(payload.get('models'), folder_paths, payload.get('prompt'))
        except (KeyError, OSError, TypeError, ValueError):
            return web.json_response({'verified': False}, status=409)
        return web.json_response(result,headers={'X-Headkit-Verification':json.dumps(session.report(),separators=(',',':'))})
