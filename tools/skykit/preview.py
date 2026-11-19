"""Render the sky shader off-screen: the real srn_sky_fs.shd and srn_sky_math.shd, with a stub in place of the
game's `inc_standard` that declares the engine values the shader reads.

Needs ModernGL and an OpenGL 3.3 context. Two cameras: `equirect` (the whole sphere, u across, v up: the fallback
picture) and `view` (a perspective camera at a yaw and pitch, as a player would see it).
"""
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SHADERS = ROOT / 'srn_skybox'

STUB = '''
#define lowp
#define mediump
#define highp
uniform sampler2D texUnit0;
uniform int worldtimerTimeOfDay;
uniform int moduleMinutesPerHour;
uniform float areaWeatherDensity;
vec2 vVertexTexCoords;
'''

PREVIEW_MAIN = '''
uniform vec4 previewCamera;   // x yaw, y pitch (radians), z vertical field of view (radians), w aspect
uniform float previewEquirect;
void main()
{
    if (previewEquirect > 0.5)
        vVertexTexCoords = screen;
    else
    {
        vec2 p = (screen * 2.0 - 1.0) * vec2(tan(previewCamera.z * 0.5) * previewCamera.w, tan(previewCamera.z * 0.5));
        float cy = cos(previewCamera.x), sy = sin(previewCamera.x), cp = cos(previewCamera.y), sp = sin(previewCamera.y);
        vec3 forward = vec3(cp * cy, cp * sy, sp);
        vec3 right = vec3(sy, -cy, 0.0);
        vec3 up = cross(right, forward);
        vec3 d = normalize(forward + p.x * right + p.y * up);
        float azimuth = atan(d.y, d.x);
        if (azimuth < 0.0) azimuth += 6.28318531;
        vVertexTexCoords = vec2(azimuth / 6.28318531, asin(clamp(d.z, -1.0, 1.0)) / 3.14159265 + 0.5);
    }
    srn_sky_main();
}
'''

VERTEX = '''
#version 120
attribute vec2 corner;
varying vec2 screen;
void main() { screen = corner * 0.5 + 0.5; gl_Position = vec4(corner, 0.0, 1.0); }
'''


def fragment_source(shaders=SHADERS):
    """The game's fragment shader made standalone: includes inlined, the engine stubbed, main renamed."""
    text = (Path(shaders) / 'srn_sky_fs.shd').read_text(encoding='ascii')
    text = text.replace('#include "inc_standard"', STUB)
    text = text.replace('#include "srn_sky_math"', (Path(shaders) / 'srn_sky_math.shd').read_text(encoding='ascii'))
    text, count = re.subn(r'void\s+main\s*\(\s*\)', 'void srn_sky_main()', text)
    if count != 1:
        raise ValueError('srn_sky_fs.shd: expected one main()')
    return '#version 120\nvarying vec2 screen;\n' + text + PREVIEW_MAIN


class Renderer:
    def __init__(self):
        import moderngl
        self.gl = moderngl.create_standalone_context(require=330)
        self.program = self.gl.program(vertex_shader=VERTEX, fragment_shader=fragment_source())
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], 'f4')
        self.vao = self.gl.vertex_array(self.program, [(self.gl.buffer(quad.tobytes()), '2f', 'corner')])
        self.textures = []

    def bind(self, halves):
        """halves: [(rgba, mask), (rgba, mask)] float arrays, top row first."""
        for texture in self.textures:
            texture.release()
        self.textures = []
        arrays = [halves[0][0], halves[1][0], halves[0][1], halves[1][1]]
        for unit, array in enumerate(arrays):
            data = np.clip(array[::-1] * 255 + 0.5, 0, 255).astype(np.uint8)
            if data.shape[2] == 3:
                data = np.dstack([data, np.full(data.shape[:2], 255, np.uint8)])
            texture = self.gl.texture((data.shape[1], data.shape[0]), 4, np.ascontiguousarray(data).tobytes())
            texture.build_mipmaps()
            texture.repeat_x = texture.repeat_y = False
            texture.use(unit)
            self.textures.append(texture)
        for unit, name in enumerate(('texUnit0', 'texUnit1', 'texUnit2', 'texUnit3')):
            if name in self.program:
                self.program[name].value = unit

    def render(self, parameters, size, *, time_ms=600000, minutes_per_hour=2, weather=0.0, camera=None, fade=1.0):
        """RGB float image (top row first). camera None renders the equirectangular sphere; else (yaw, pitch, fov) degrees."""
        width, height = size
        for name, value in parameters.items():
            if name in self.program:
                self.program[name].value = tuple(float(v) for v in value) if isinstance(value, (tuple, list)) else float(value)
        values = {'worldtimerTimeOfDay': int(time_ms), 'moduleMinutesPerHour': int(minutes_per_hour),
                  'areaWeatherDensity': float(weather) * 100.0, 'globalColor': (1.0, 1.0, 1.0, fade)}
        for name, value in values.items():
            if name in self.program:
                self.program[name].value = value
        if camera is None:
            self.program['previewEquirect'].value = 1.0
        else:
            yaw, pitch, fov = camera
            self.program['previewEquirect'].value = 0.0
            self.program['previewCamera'].value = (np.radians(yaw), np.radians(pitch), np.radians(fov), width / height)
        target = self.gl.simple_framebuffer((width, height), components=4)
        target.use()
        target.clear(0, 0, 0, 0)
        self.vao.render(mode=0x0005)  # triangle strip
        data = np.frombuffer(target.read(components=4), np.uint8).reshape(height, width, 4)[::-1]
        target.release()
        return data.astype(np.float32) / 255
