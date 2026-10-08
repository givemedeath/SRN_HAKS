"""Installed material semantics, original normal decode and channel transport."""
import unittest

import numpy as np

from audit_target_material_shaders import normal_diagnostics, prove_shader_semantics, shader_roughness, transport_roughness


def shader_fixture():
    return {
        'fslit_nm.shd': '#define SHADER_TYPE 2\n#define NORMAL_MAP 1\n#define ROUGHNESS_MAP 1\n#define ENVIRONMENT_MAP 0\n',
        'inc_material.shd': '''#define MATERIAL_READ_ROUGHNESS_FROM_SPECULAR_MAP 0
#define fGeneratedRoughnessMax 0.55
#define fGeneratedRoughnessMin 0.125
if(Roughness>0.0)
{
    MATERIAL_ROUGHNESS_VALUE = Roughness;
}
MATERIAL_ROUGHNESS_VALUE = texture2D(texUnit3, vTexCoords.xy).r;
''',
        'inc_standard.shd': '''vFragmentNormal.xy = texture2D(texUnit1, vTexCoords).rg * 2.0 - 1.0;
vFragmentNormal.z = sqrt(max(1.0 - dot(vFragmentNormal.xy, vFragmentNormal.xy),0.0));
vFragmentNormal = mTSB * vFragmentNormal;
''',
        'inc_lighting.shd': '''fRoughness_sq = MATERIAL_ROUGHNESS_VALUE * MATERIAL_ROUGHNESS_VALUE;
float fFactor = fCosNormalFacet * fCosNormalFacet * -fRoughness_sq_inv + 1.0;
return fRoughness_sq / (fFactor * fFactor);
''',
        'inc_config.shd': '#define SPECULAR_DISTRIBUTION_MODEL 1\n',
        'fs_pltgen.shd': '''ColorPLT.g = PLTscheme[int(ColorPLT.g*255.0+0.5)];
ColorPLT = texture2D(texUnit1, ColorPLT.rg);
''',
    }


class TargetMaterialShaderTests(unittest.TestCase):
    def test_roughness_zero_sentinel_and_positive_override_are_distinct(self):
        self.assertEqual(shader_roughness(0, .37), .37)
        self.assertEqual(shader_roughness(.2, .37), .2)
        self.assertEqual(shader_roughness(0, 0), 0)
        self.assertEqual(shader_roughness(0), .55)
        self.assertEqual(shader_roughness(0, .37, shader_type=1), .55)
        self.assertAlmostEqual(shader_roughness(0, specular_texture_bound=True), .51668)
        for uniform in [-.1, .0001, 1.1, float('nan')]:
            with self.subTest(uniform=uniform), self.assertRaises(ValueError):
                shader_roughness(uniform, .37)

    def test_linear_orm_green_factor_preserves_authored_zeros(self):
        orm = np.array([[[249, 0, 50], [5, 170, 240], [128, 255, 0]]], dtype='u1')
        encoded, proof = transport_roughness(orm, .6)
        np.testing.assert_array_equal(encoded, [[0, 102, 153]])
        self.assertFalse(proof['gammaApplied']); self.assertEqual(proof['zeroTexels'], 1)
        self.assertLessEqual(proof['maximumQuantizationError'], .5/255)
        # Altering occlusion or metallic channels must have no effect on roughness.
        edited = orm.copy(); edited[..., 0] = 0; edited[..., 2] = 255
        np.testing.assert_array_equal(transport_roughness(edited, .6)[0], encoded)
        # The documented unit interval includes factor 0: report it, do not clamp.
        self.assertEqual(transport_roughness(orm, 0)[1]['zeroTexels'], 3)
        for factor in [-.1, 1.1, float('inf')]:
            with self.assertRaises(ValueError): transport_roughness(orm, factor)

    def test_byte_quantization_and_small_roughness_are_measured(self):
        orm = np.zeros((1, 256, 3), dtype='u1'); orm[0, :, 1] = np.arange(256)
        encoded, proof = transport_roughness(orm, .5)
        np.testing.assert_array_equal(encoded, np.rint(np.arange(256)*.5)[None, :].astype('u1'))
        self.assertEqual(proof['zeroTexels'], 2)
        self.assertAlmostEqual(proof['maximumQuantizationError'], .5/255)

    def test_nwn_normal_decode_ignores_blue_but_reports_render_divergence(self):
        first = np.array([[[128, 128, 255], [210, 100, 220]]], dtype='u1')
        second = first.copy(); second[..., 2] = 130
        before = normal_diagnostics(first); after = normal_diagnostics(second)
        self.assertEqual(before['xyRadiusSquaredMaximum'], after['xyRadiusSquaredMaximum'])
        self.assertEqual(before['nwnTangentNormalLengthRange'], after['nwnTangentNormalLengthRange'])
        self.assertGreater(after['normalizedGltfToNwnAngularDegreesMaximum'],
                           before['normalizedGltfToNwnAngularDegreesMaximum'])
        self.assertNotEqual(before['originalRgbSha256'], after['originalRgbSha256'])
        self.assertFalse(before['edited']); self.assertFalse(before['clientLightingAccepted'])
        with self.assertRaisesRegex(ValueError, 'strength one'): normal_diagnostics(first, .35)

    def test_normal_rg_outside_disk_is_reported_without_normalization_or_edit(self):
        pixels = np.array([[[255, 255, 255], [128, 128, 0]]], dtype='u1'); copy = pixels.copy()
        proof = normal_diagnostics(pixels)
        self.assertEqual(proof['xyOutsideUnitDiskTexels'], 1)
        self.assertEqual(proof['nonPositiveAuthoredZTexels'], 1)
        self.assertAlmostEqual(proof['nwnTangentNormalLengthRange'][1], np.sqrt(2))
        self.assertGreater(proof['normalizedGltfToNwnAngularDegreesMaximum'], 179)
        np.testing.assert_array_equal(pixels, copy)

    def test_static_source_audit_rejects_changed_channel_or_multiplier(self):
        proof = prove_shader_semantics(shader_fixture())
        self.assertTrue(proof['roughness']['positiveUniformOverridesMap'])
        self.assertFalse(proof['normal']['blueRead'])
        for resource, previous, replacement in [
            ('inc_material.shd', 'MATERIAL_ROUGHNESS_VALUE = Roughness;', 'MATERIAL_ROUGHNESS_VALUE *= Roughness;'),
            ('inc_material.shd', 'texUnit3, vTexCoords.xy).r;', 'texUnit3, vTexCoords.xy).g;'),
            ('inc_standard.shd', ').rg * 2.0', ').rgb * 2.0'),
            ('inc_config.shd', 'MODEL 1', 'MODEL 0'),
        ]:
            sources = shader_fixture(); sources[resource] = sources[resource].replace(previous, replacement)
            with self.subTest(resource=resource, replacement=replacement), self.assertRaises(ValueError):
                prove_shader_semantics(sources)


if __name__ == '__main__': unittest.main()
