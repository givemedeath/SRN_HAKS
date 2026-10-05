"""Explicit Blender diagnostic render settings; CPU mode never selects a GPU."""


def apply_render_settings(scene, engine):
    if engine=='eevee':
        scene.render.engine='BLENDER_EEVEE'
        scene.eevee.use_gtao=True
        scene.eevee.gtao_distance=.08
        return {'requested':'eevee','blenderEngine':'BLENDER_EEVEE',
                'ambientOcclusion':True,'gtaoDistance':.08,'clientEvidence':False}
    if engine!='cycles-cpu':
        raise ValueError('Unknown offline preview render engine: '+engine)
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=16
    scene.cycles.use_denoising=True
    scene.cycles.denoiser='OPENIMAGEDENOISE'
    scene.render.threads_mode='FIXED'
    scene.render.threads=4
    return {'requested':'cycles-cpu','blenderEngine':'CYCLES','device':'CPU',
            'samples':16,'threadsMode':'FIXED','threads':4,
            'denoising':True,'denoiser':'OPENIMAGEDENOISE','clientEvidence':False}
