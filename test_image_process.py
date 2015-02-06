# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from PIL import Image, ImageChops
from pelican.tests.support import unittest, get_settings, temporary_folder

from image_process import images, harvest_images, process_images


CUR_DIR = os.path.dirname(__file__)
TEST_IMAGES = [os.path.join(CUR_DIR, 'test_data/pelican-bird.jpg'), os.path.join(CUR_DIR, 'test_data/pelican-bird.png')]

class Pelican(object):
    def __init__(self, settings):
        self.settings = settings

class Instance(object):
    def __init__(self, content, settings):
        self._content = content
        self.settings = settings

class ImageDerivativeTest(unittest.TestCase):
    transforms = {
        'crop': ['crop 10 20 100 200'],
        'flip_horizontal': ['flip_horizontal'],
        'flip_vertical': ['flip_vertical'],
        'grayscale': ['grayscale'],
        'resize': ['resize 200 250'],
        'rotate': ['rotate 20'],
        'scale_in': ['scale_in 200 250'],
        'scale_out': ['scale_out 200 250'],
        'blur': ['blur'],
        'contour': ['contour'],
        'detail':['detail'],
        'edge_enhance': ['edge_enhance'],
        'edge_enhance_more': ['edge_enhance_more'],
        'emboss': ['emboss'],
        'find_edges': ['find_edges'],
        'smooth': ['smooth'],
        'smooth_more': ['smooth_more'],
        'sharpen': ['sharpen'],
        }

    def test_extraction(self):
        html = '<html> <body> <img class="test image-process image-process-crop test2" src="/tmp/test.jpg" /> </body> </html>'
        c = Instance(html, get_settings(IMAGE_PROCESS = self.transforms))

        del images[:]
        harvest_images(c)

        expected_content = '<html> <body> <img class="test image-process image-process-crop test2" src="/tmp/derivatives/crop/test.jpg"/> </body> </html>'
        expected_images = [(u'output/tmp/test.jpg', u'output/tmp/derivatives/crop/test.jpg', 'crop')]

        self.assertEqual(c._content, expected_content)
        self.assertEqual(images, expected_images)


    def test_transforms(self):
        p = Pelican(get_settings(IMAGE_PROCESS = self.transforms))
        del images[:]
        with temporary_folder() as tmpdir:
            for d in self.transforms:
                for i in TEST_IMAGES:
                    _, name = os.path.split(i)
                    destination = os.path.join(tmpdir, d, name)
                    images.append((i, destination, d))
            process_images(p)

            for i in images:
                transformed = Image.open(i[1])

                path, name = os.path.split(i[0])
                expected_path = os.path.join(path, 'results', i[2], name)
                expected = Image.open(expected_path)

                self.assertEqual(ImageChops.difference(transformed, expected).getbbox(), None)


if __name__ == '__main__':
    unittest.main()
