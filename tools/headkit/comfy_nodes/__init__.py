"""Comfy adapter with controlled-session and fresh deployment/runtime-file verification."""
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
    from .managed_startup import session_context
    from .verification import HEAVY_VERIFICATION_LOCK, verification_pass
    from aiohttp import web
    from server import PromptServer
    import nodes as comfy_core_nodes

    NODE_CLASS_MAPPINGS.update(verified_loader_mappings(comfy_core_nodes.NODE_CLASS_MAPPINGS, folder_paths))

    from .attested import attested_context, attested_inventory, attested_session, unmanaged
    from .source_snapshot import same_inventory

    def _capture_attested():
        # A ComfyUI another program started (Comfy Desktop): record what it runs; the client compares it with an
        # approved snapshot. A failed controlled session never falls back to this.
        try:
            with HEAVY_VERIFICATION_LOCK, verification_pass('server-startup-attested') as audit:
                with audit.phase('launch'):
                    session = attested_session(folder_paths)
                with audit.phase('deployment'):
                    inventory = attested_inventory(folder_paths)
                with audit.phase('runtime-files'):
                    identity = capture_runtime_identity(folder_paths, inventory, session=session)
            return inventory, session, identity
        except Exception:
            logging.getLogger(__name__).exception('Headkit attested baseline capture failed; dispatch remains blocked')
            return None, None, None

    def _capture_startup():
        if unmanaged():
            return _capture_attested()
        try:
            with HEAVY_VERIFICATION_LOCK, verification_pass('server-startup') as audit:
                with audit.phase('deployment'):
                    session, config = session_context(folder_paths.base_path)
                inventory = config['inventory']
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
                    if _STARTUP_SESSION.get('mode') == 'attested':
                        # No frozen deployment to re-verify: the census itself must still match what was loaded.
                        session = attested_context(folder_paths, _STARTUP_SESSION)
                        if not same_inventory(attested_inventory(folder_paths), _STARTUP_COMFY_SOURCE_INVENTORY):
                            raise ValueError('Comfy source files changed after the adapter loaded; restart ComfyUI')
                    else:
                        session, config = session_context(folder_paths.base_path)
                    if session != _STARTUP_SESSION:
                        raise ValueError('Controlled Comfy session changed; prepare again')
                with audit.phase('runtime-files'):
                    current = capture_runtime_identity(folder_paths, _STARTUP_COMFY_SOURCE_INVENTORY, session=session)
                    # An attested server keeps loading after the adapter (later custom nodes, the server, Manager),
                    # so its import-time census is no baseline: the client compares each fresh census with the
                    # approved snapshot and lists any difference (headkit/attestation.py).
                    if _STARTUP_SESSION.get('mode') != 'attested' and not same_runtime_environment(current, _STARTUP_RUNTIME_IDENTITY):
                        raise ValueError('Comfy server runtime files changed after the adapter loaded')
        except Exception:
            logging.getLogger(__name__).exception('Headkit live runtime verification failed; dispatch remains blocked')
            return web.json_response({'verified': False}, status=409)
        return web.json_response(current, headers={'X-Headkit-Verification': json.dumps(audit.report(), separators=(',', ':'))})

    @PromptServer.instance.routes.get('/headkit/preparation-identity')
    async def headkit_preparation_identity(request):
        # This is a planning baseline, never evidence of current loaded state.
        # Submission and completion use the full runtime-identity endpoint.
        if _STARTUP_RUNTIME_IDENTITY is None:
            return web.json_response({'verified': False}, status=409)
        if _STARTUP_SESSION.get('mode') == 'attested':
            # No import-time baseline stands for an attested server: plan against its verified current identity.
            response = await verify_headkit_runtime_identity(request)
            if response.status != 200: return response
            return web.json_response({'kind': 'preparation-baseline-v1', 'runtimeIdentity': json.loads(response.body),
                                      'requiresFreshDispatch': True})
        return web.json_response({'kind': 'preparation-baseline-v1',
            'runtimeIdentity': _STARTUP_RUNTIME_IDENTITY, 'requiresFreshDispatch': True})

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
