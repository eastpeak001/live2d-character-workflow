"""Run from the repository root: python -m unittest discover -s tests."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from psd_tools import PSDImage

SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'live2d-character-workflow'
sys.path.insert(0, str(SKILL / 'scripts'))
from bind_model import bind, field, warp_points, WARP_CLASSES
from cubism_archive import Archive
from motion_keys import make
from starter import create


class WorkflowTests(unittest.TestCase):
    def test_original_practice_model_and_motion(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'practice'
            create(folder)
            psd = PSDImage.open(folder/'Mobile.psd')
            self.assertEqual([layer.name for layer in psd], ['Stand', 'Ribbon', 'Pendant'])
            neutral = folder/'Neutral.cmo3'
            specs = json.loads((folder/'rig.json').read_text())['controls']
            model_file = folder/'Mobile.cmo3'
            bind(neutral, specs, model_file, folder/'Mobile.psd')
            xml = Archive(model_file.read_bytes()).xml()
            self.assertTrue(all(cls.encode() + b'?>' in xml for cls in WARP_CLASSES))
            scene = ET.fromstring(xml)
            self.assertEqual({n.text for n in scene.findall(".//file[@xs.n='psdFile']")}, {'Mobile.psd'})
            warps = scene.findall("./shared/CWarpDeformerSource")
            self.assertEqual(len(warps), 2)
            parent = field(field(warps[0], 'super'), 'guid').get('xs.ref')
            self.assertEqual(field(field(warps[1], 'super'), 'targetDeformerGuid').get('xs.ref'), parent)
            for warp in warps:
                poses = [field(form, 'positions').text for form in field(warp, 'keyforms')]
                self.assertEqual(len(set(poses)), 3)
            motion = json.loads((folder/'Swing.motion3.json').read_text())
            self.assertEqual([c['Id'] for c in motion['Curves']], ['ParamSwing', 'ParamTip'])
            self.assertEqual((motion['Meta']['Duration'], motion['Meta']['Fps']), (2.0, 48))
            for curve in motion['Curves']:
                v = curve['Segments']
                self.assertEqual(v[1], v[-1])
                start_tangent = (v[4]-v[1]) / (v[3]-v[0])
                end_tangent = (v[-1]-v[-3]) / (v[-2]-v[-4])
                self.assertAlmostEqual(start_tangent, end_tangent, places=5)
            with self.assertRaisesRegex(ValueError, 'already attached'):
                bind(neutral, specs + [dict(specs[0], id='ParamExtra')], folder/'invalid.cmo3')
            self.assertFalse((folder/'invalid.cmo3').exists())

    def test_anchoring_and_loop_endpoint(self):
        spec = {'move': [.2, .1], 'weight_y': [1, 0]}
        points = list(warp_points(spec, (200, 250), (2, 4), 1, False))
        self.assertEqual(points[-1], (200, 250))
        self.assertEqual(points[0], (40, 25))
        with self.assertRaisesRegex(ValueError, 'both ends'):
            make({'fps': 30, 'frames': 10, 'tracks': {'A': {'keys': [[0, 0], [10, 1]]}}})


if __name__ == '__main__':
    unittest.main()
