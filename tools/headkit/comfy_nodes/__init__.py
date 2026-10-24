"""Comfy adapter with controlled deployment and fresh loaded-code verification."""
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
    from .runtime_identity import capture_runtime_identity, same_runtime_environment
    from .source_snapshot import loaded_source_code
    from .managed_startup import session_context
    from .verification import HEAVY_VERIFICATION_LOCK, verification_pass
    from aiohttp import web
    from server import PromptServer
    import nodes as comfy_core_nodes

    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))

    def _capture_startup():
        try:
            with HEAVY_VERIFICATION_LOCK, verification_pass('server-startup') as audit:
                with audit.phase('deployment'):
                    session, config = session_context(folder_paths.base_path)
                inventory = config['inventory']
                with audit.phase('loaded-code'):
                    loaded_source_code(inventory['roots'])
                with audit.phase('runtime-files'):
                    identity = capture_runtime_identity(folder_paths, inventory, session=session)
                declared = {(row['path'], row['sha256']) for row in config['runtime']['files']}
                if any((row['path'], row['sha256']) not in declared for row in identity['files']):
                    raise ValueError('Executing runtime contains files outside the frozen deployment')
            return inventory, session, identity
        except Exception:
            logging.getLogger(__name__).exception('Headkit runtime baseline capture failed; dispatch remains blocked')
            return None, None, None

    (_STARTUP_COMFY_SOURCE_INVENTORY,
     _STARTUP_SESSION,
     _STARTUP_RUNTIME_IDENTITY) = _capture_startup()

    @PromptServer.instance.routes.get('/headkit/runtime-identity')
    async def verify_headkit_runtime_identity(request):
        try:
            if _STARTUP_RUNTIME_IDENTITY is None:
                raise ValueError('Use a new controlled Comfy session; leave other sessions untouched')
            with HEAVY_VERIFICATION_LOCK, verification_pass('server-request') as audit:
                with audit.phase('deployment'):
                    session, config = session_context(folder_paths.base_path)
                    if session != _STARTUP_SESSION:
                        raise ValueError('Controlled Comfy session changed; prepare again')
                with audit.phase('loaded-code'):
                    loaded_source_code(_STARTUP_COMFY_SOURCE_INVENTORY['roots'])
                with audit.phase('runtime-files'):
                    current = capture_runtime_identity(folder_paths, _STARTUP_COMFY_SOURCE_INVENTORY, session=session)
                    if not same_runtime_environment(current, _STARTUP_RUNTIME_IDENTITY):
                        raise ValueError('Comfy server runtime files changed after the adapter loaded')
        except Exception:
            logging.getLogger(__name__).exception('Headkit live runtime verification failed; dispatch remains blocked')
            return web.json_response({'verified': False}, status=409)
        return web.json_response(current, headers={'X-Headkit-Verification': json.dumps(audit.report(), separators=(',', ':'))})

    @PromptServer.instance.routes.post('/headkit/verify-loader-models')
    async def verify_headkit_loader_models(request):
        try:
            payload = await request.json()
            with HEAVY_VERIFICATION_LOCK, verification_pass('server-models') as audit:
                result = verify_loader_models(payload.get('models'), folder_paths, payload.get('prompt'))
        except Exception:
            logging.getLogger(__name__).exception('Headkit loader model verification failed; dispatch remains blocked')
            return web.json_response({'verified': False}, status=409)
        return web.json_response(result, headers={'X-Headkit-Verification': json.dumps(audit.report(), separators=(',', ':'))})
