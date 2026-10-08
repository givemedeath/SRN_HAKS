"""Regression checks for complete multiview framing and fail-closed layout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw


class FramingTests(unittest.TestCase):
    def run_normalizer(self, source, target, components=False, six=False, end_ratio=None, columns=2, opaque=False, order=None, axial=None):
        command = [sys.executable, str(Path(__file__).with_name('normalize_part_turnaround.py')),
                   '--source', str(source), '--output', str(target), '--notes', 'layout regression']
        if components: command.append('--layout-components')
        if six: command.extend(['--six-views', '--center-origin'])
        if end_ratio is not None: command.extend(['--end-view-min-area-ratio', str(end_ratio)])
        command.extend(['--layout-columns', str(columns)])
        if opaque: command.append('--opaque-black-background')
        if order: command.extend(['--view-order', order])
        if axial: command.extend(['--axial-source', str(axial)])
        return subprocess.run(command, capture_output=True, text=True)

    def sheet(self, path, extra=False):
        image = Image.new('RGBA', (400, 400))
        draw = ImageDraw.Draw(image)
        # Wide left objects cross the fixed midline, but do not meet right views.
        for box in [(20, 30, 210, 140), (245, 30, 350, 140),
                    (20, 240, 210, 350), (245, 240, 350, 350)]:
            draw.ellipse(box, fill=(180, 120, 80, 255))
        if extra: draw.rectangle((180, 160, 235, 215), fill=(255, 255, 255, 255))
        image.save(path)

    def test_cross_midline_preserves_width_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/'sheet.png'; self.sheet(source)
            clipped = self.run_normalizer(source, root/'clipped')
            self.assertNotEqual(clipped.returncode, 0)
            self.assertIn('Silhouette touches quadrant boundary', clipped.stderr)
            result = self.run_normalizer(source, root/'complete', True)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads((root/'complete/provenance.json').read_text())
            self.assertEqual(record['views']['front']['panelCrop'], [20, 30, 211, 141])
            front = record['views']['front']['normalizedBounds'][2]
            left = record['views']['left']['normalizedBounds'][2]
            self.assertLess(abs(front / left - 191 / 106), .004)
            for view in ('front','left','back','right'):
                with Image.open(root/'complete'/f'{view}.png') as image:
                    self.assertEqual(image.size, (1024,1024))

    def test_opaque_and_ambiguous_extra_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); opaque = root/'opaque.png'
            Image.new('RGB', (400,400), 'white').save(opaque)
            result = self.run_normalizer(opaque, root/'opaque-result', True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Meaningful transparent alpha', result.stderr)
            source = root/'extra.png'; self.sheet(source, True)
            result = self.run_normalizer(source, root/'extra-result', True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Ambiguous extra substantial component', result.stderr)

    def test_six_cameras_share_scale_and_centered_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'six.png'
            image=Image.new('RGBA',(600,900)); draw=ImageDraw.Draw(image)
            for i, (width,height) in enumerate(((110,200),(220,160),(110,200),(220,160),(140,240),(140,240))):
                x=(i%2)*300+150; y=(i//2)*300+150
                draw.ellipse((x-width//2,y-height//2,x+width//2,y+height//2),fill=(180,120,80,255))
            image.save(source)
            result=self.run_normalizer(source,root/'normalized',True,True)
            self.assertEqual(result.returncode,0,result.stderr)
            record=json.loads((root/'normalized/provenance.json').read_text())
            self.assertEqual(set(record['views']),{'front','left','back','right','top','bottom'})
            for view,data in record['views'].items():
                x,y,w,h=data['normalizedBounds']
                self.assertLessEqual(abs(x+w/2-512),.5)
                self.assertLessEqual(abs(y+h/2-512),.5)
            self.assertLess(abs(record['views']['front']['normalizedBounds'][2]/record['views']['left']['normalizedBounds'][2]-111/221),.004)

    def test_missing_sixth_view_fails_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'five.png'
            image=Image.new('RGBA',(600,900)); draw=ImageDraw.Draw(image)
            for i in range(5):
                x=(i%2)*300+50; y=(i//2)*300+50
                draw.rectangle((x,y,x+190,y+190),fill=(180,120,80,255))
            image.save(source)
            result=self.run_normalizer(source,root/'out',True,True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((root/'out').exists())

    def elongated_sheet(self, path, small_front=False, extra=False, clipped=False):
        image=Image.new('RGBA',(600,900)); draw=ImageDraw.Draw(image)
        for i in range(6):
            x=(i%2)*300+150; y=(i//2)*300+150
            width,height=(80,240) if i<4 else (66,66)
            if small_front and i==0: width,height=66,66
            if clipped and i==4: x=30
            draw.rectangle((x-width//2,y-height//2,x+width//2,y+height//2),fill=(180,120,80,255))
        if extra: draw.rectangle((5,290,55,325),fill=(180,120,80,255))
        image.save(path)

    def test_explicit_small_axial_views_without_weakening_side_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'sheet.png'; self.elongated_sheet(source)
            default=self.run_normalizer(source,root/'default',True,True)
            self.assertNotEqual(default.returncode,0)
            result=self.run_normalizer(source,root/'accepted',True,True,.22)
            self.assertEqual(result.returncode,0,result.stderr)
            record=json.loads((root/'accepted/provenance.json').read_text())
            self.assertEqual(record['componentAreas']['front']['minimumAreaRatio'],.25)
            self.assertEqual(record['componentAreas']['top']['minimumAreaRatio'],.22)
            self.elongated_sheet(source,small_front=True)
            result=self.run_normalizer(source,root/'small-front',True,True,.22)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('for front',result.stderr)
            self.assertFalse((root/'small-front').exists())

    def test_axial_override_retains_extra_and_boundary_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'sheet.png'
            self.elongated_sheet(source,extra=True)
            result=self.run_normalizer(source,root/'extra',True,True,.22)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Ambiguous extra substantial component',result.stderr)
            self.elongated_sheet(source,clipped=True)
            result=self.run_normalizer(source,root/'clipped',True,True,.20)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('source boundary',result.stderr)

    def test_explicit_observed_three_column_sheet_keeps_view_assignment(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'sheet.png'
            image=Image.new('RGBA',(900,600)); draw=ImageDraw.Draw(image)
            for i in range(6):
                x=(i%3)*300+150; y=(i//3)*300+150
                draw.rectangle((x-70,y-90,x+70,y+90),fill=(100+i*20,120,80,255))
            image.save(source)
            result=self.run_normalizer(source,root/'out',True,True,columns=3)
            self.assertEqual(result.returncode,0,result.stderr)
            record=json.loads((root/'out/provenance.json').read_text())
            self.assertEqual(record['layout'],'3x2: front,left,back/right,top,bottom')
            self.assertEqual(record['views']['back']['panelCrop'],[680,60,821,241])
            self.assertEqual(record['views']['right']['panelCrop'],[80,360,221,541])


    def test_black_source_observed_order_and_foreground_intensity_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'sheet.png'
            image=Image.new('RGB',(600,900),'black');draw=ImageDraw.Draw(image)
            colors=[]
            for i in range(6):
                x=(i%2)*300+150;y=(i//2)*300+150;color=(90+i*20,100,70);colors.append(color)
                draw.rectangle((x-70,y-90,x+70,y+90),fill=color)
            image.save(source)
            result=self.run_normalizer(source,root/'out',True,True,opaque=True,order='front,back,left,right,top,bottom')
            self.assertEqual(result.returncode,0,result.stderr)
            record=json.loads((root/'out/provenance.json').read_text())
            self.assertEqual(record['views']['back']['panelCrop'],[380,60,521,241])
            self.assertEqual(record['views']['left']['panelCrop'],[80,360,221,541])
            self.assertEqual(Image.open(root/'out/back.png').getpixel((512,512)),colors[1])
            self.assertEqual(record['observedViewOrder'],['front','back','left','right','top','bottom'])
            bad=self.run_normalizer(source,root/'duplicate',True,True,opaque=True,order='front,front,left,right,top,bottom')
            self.assertNotEqual(bad.returncode,0);self.assertFalse((root/'duplicate').exists())
            draw.rectangle((0,0,20,20),fill='white');image.save(source)
            bad=self.run_normalizer(source,root/'border',True,True,opaque=True)
            self.assertNotEqual(bad.returncode,0);self.assertIn('black outer border',bad.stderr)


    def test_axial_camera_descendant_keeps_approved_cardinal_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';axial=root/'axial.png'
            self.elongated_sheet(source)
            image=Image.open(source).convert('RGBA');draw=ImageDraw.Draw(image)
            # Different skin color in the descendant's entire sheet must affect
            # only the explicitly selected axial row.
            for i in range(6):
                x=(i%2)*300+150;y=(i//2)*300+150;width,height=(80,240) if i<4 else (66,66)
                draw.rectangle((x-width//2,y-height//2,x+width//2,y+height//2),fill=(70,160,190,255))
            image.save(axial)
            result=self.run_normalizer(source,root/'out',True,True,.22,axial=axial)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(Image.open(root/'out/front.png').getpixel((512,512)),(180,120,80))
            self.assertEqual(Image.open(root/'out/top.png').getpixel((512,512)),(70,160,190))
            record=json.loads((root/'out/provenance.json').read_text())
            self.assertFalse(record['auxiliarySources']['axial']['cardinalSourcePixelsReplaced'])
            self.assertEqual((root/'out/source.png').read_bytes(),source.read_bytes())


    def crossing_axial_sheet(self, path, auxiliary=False, opaque=False):
        image = Image.new('RGB' if opaque else 'RGBA', (600,900), 'black' if opaque else (0,0,0,0))
        draw = ImageDraw.Draw(image)
        for i in range(6):
            x = (i%2)*300+150
            y = (i//2)*300+(200 if i//2 == 1 else 150)
            # Primary side components extend to y=660, crossing the nominal
            # axial row at y=600. Auxiliary cardinals have different silhouettes.
            width,height = ((110,180) if i<4 else (180,140)) if auxiliary else ((110,260) if i<2 else (110,320) if i<4 else (140,140))
            color = (70+i*10,160,190) if auxiliary else (180,120+i*10,80)
            draw.rectangle((x-width//2,y-height//2,x+width//2,y+height//2),fill=color if opaque else color+(255,))
        image.save(path)

    def test_complete_auxiliary_selection_preserves_crossing_cardinals(self):
        for opaque in (False, True):
            with self.subTest(opaque=opaque), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'source.png';axial=root/'axial.png'
                self.crossing_axial_sheet(source,opaque=opaque)
                self.crossing_axial_sheet(axial,auxiliary=True,opaque=opaque)
                baseline=self.run_normalizer(source,root/'primary',True,True,opaque=opaque)
                candidate=self.run_normalizer(source,root/'combined',True,True,opaque=opaque,axial=axial)
                self.assertEqual(baseline.returncode,0,baseline.stderr)
                self.assertEqual(candidate.returncode,0,candidate.stderr)
                original=json.loads((root/'primary/provenance.json').read_text())
                combined=json.loads((root/'combined/provenance.json').read_text())
                self.assertEqual(original['scale'],combined['scale'])
                for name in ('front','left','back','right'):
                    with Image.open(root/'primary'/f'{name}.png') as a, Image.open(root/'combined'/f'{name}.png') as b:
                        self.assertEqual(a.tobytes(),b.tobytes(),name)
                    with Image.open(root/'primary'/f'{name}-alpha.png') as a, Image.open(root/'combined'/f'{name}-alpha.png') as b:
                        self.assertEqual(a.tobytes(),b.tobytes(),name+' alpha')
                    self.assertEqual(original['views'][name]['panelCrop'],combined['views'][name]['panelCrop'])
                    self.assertEqual(combined['views'][name]['source'],str(source.resolve()))
                self.assertGreater(combined['views']['back']['panelCrop'][3],600)
                self.assertEqual(combined['views']['top']['source'],str(axial.resolve()))
                self.assertEqual(Image.open(root/'combined/top.png').getpixel((512,512)),(110,160,190))
                self.assertEqual(combined['auxiliarySources']['axial']['usedViews'],['top','bottom'])
                self.assertIn('independently validated',combined['auxiliarySources']['axial']['selectionMethod'])

    def test_auxiliary_sheet_ambiguity_and_boundary_fail_closed(self):
        for defect, message in (('extra','Ambiguous extra substantial component'),
                                ('boundary','source boundary'), ('duplicate','same view')):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'source.png';axial=root/'axial.png'
                self.crossing_axial_sheet(source)
                self.crossing_axial_sheet(axial,auxiliary=True)
                image=Image.open(axial).convert('RGBA');draw=ImageDraw.Draw(image)
                if defect=='extra':draw.rectangle((255,620,290,665),fill=(255,255,255,255))
                if defect=='boundary':draw.rectangle((0,680,150,820),fill=(255,255,255,255))
                if defect=='duplicate':
                    draw.rectangle((350,650,550,850),fill=(0,0,0,0))
                    draw.rectangle((5,670,50,830),fill=(255,255,255,255))
                image.save(axial)
                result=self.run_normalizer(source,root/'out',True,True,axial=axial)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(message,result.stderr)
                self.assertFalse((root/'out').exists())

    def test_auxiliary_validation_covers_unselected_cardinals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';axial=root/'axial.png'
            self.crossing_axial_sheet(source);self.crossing_axial_sheet(axial,auxiliary=True,opaque=True)
            image=Image.open(axial);ImageDraw.Draw(image).rectangle((0,10,30,40),fill='white');image.save(axial)
            # The primary cardinals are valid. An invalid auxiliary sheet cannot
            # hide an unselected boundary component behind complete primary views.
            result=self.run_normalizer(source,root/'out',True,True,opaque=True,axial=axial)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('black outer border',result.stderr)
            self.assertFalse((root/'out').exists())

    def test_selected_union_keeps_global_substantial_area_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';axial=root/'axial.png'
            self.crossing_axial_sheet(source)
            image=Image.new('RGBA',(600,900));draw=ImageDraw.Draw(image)
            for i in range(6):
                x=(i%2)*300+150;y=(i//2)*300+150
                draw.rectangle((x-40,y-40,x+40,y+40),fill=(100,150,180,255))
            image.save(axial)
            result=self.run_normalizer(source,root/'out',True,True,axial=axial)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('for top',result.stderr)
            self.assertFalse((root/'out').exists())

    def test_axial_source_size_mismatch_fails_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.png';axial=root/'axial.png'
            self.crossing_axial_sheet(source)
            Image.new('RGBA',(601,900)).save(axial)
            result=self.run_normalizer(source,root/'out',True,True,axial=axial)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('original sheet dimensions',result.stderr)
            self.assertFalse((root/'out').exists())


if __name__ == '__main__': unittest.main()
