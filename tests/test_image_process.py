# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import unittest
from contextlib import contextmanager
from shutil import rmtree
from tempfile import mkdtemp

import pelican_image_process
from pelican_image_process import (
    harvest_images_in_fragment,
    process_image,
)

# from pelican.tests.support import get_settings, temporary_folder, unittest
from PIL import Image, ImageChops

try:
    import unittest.mock as mock  # python < 3.3
except ImportError:
    import mock


CUR_DIR = os.path.dirname(__file__)
TEST_IMAGES = [
    os.path.join(CUR_DIR, "test_data/pelican-bird.jpg"),
    os.path.join(CUR_DIR, "test_data/pelican-bird.png"),
]


def get_settings(**kwargs):
    """Provide tweaked setting dictionaries for testing
    Set keyword arguments to override specific settings.
    """
    DEFAULT_CONFIG = {
        "PATH": os.path.join(os.path.dirname(__file__)),
        "OUTPUT_PATH": "output",
        "static_content": {},
        "filenames": {},
        "SITEURL": "//",
    }
    settings = DEFAULT_CONFIG.copy()
    for key, value in kwargs.items():
        settings[key] = value
    return settings


@contextmanager
def temporary_folder():
    """creates a temporary folder, return it and delete it afterwards.
    This allows to do something like this in tests:
        >>> with temporary_folder() as d:
            # do whatever you want
    """
    tempdir = mkdtemp()
    try:
        yield tempdir
    finally:
        rmtree(tempdir)


class ImageDerivativeTest(unittest.TestCase):
    transforms = {
        "crop": ["crop 10 20 100 200"],
        "flip_horizontal": ["flip_horizontal"],
        "flip_vertical": ["flip_vertical"],
        "grayscale": ["grayscale"],
        "resize": ["resize 200 250"],
        "rotate": ["rotate 20"],
        "scale_in": ["scale_in 200 250 False"],
        "scale_out": ["scale_out 200 250 False"],
        "blur": ["blur"],
        "contour": ["contour"],
        "detail": ["detail"],
        "edge_enhance": ["edge_enhance"],
        "edge_enhance_more": ["edge_enhance_more"],
        "emboss": ["emboss"],
        "find_edges": ["find_edges"],
        "smooth": ["smooth"],
        "smooth_more": ["smooth_more"],
        "sharpen": ["sharpen"],
    }

    @mock.patch("pelican_image_process.process_image")
    def test_extraction(self, process_image):

        settings = get_settings(
            IMAGE_PROCESS_DIR="derivatives", IMAGE_PROCESS=self.transforms
        )
        html = (
            '<img class="test image-process image-process-crop test2"'
            ' src="/tmp/test.jpg" />'
        )

        html = harvest_images_in_fragment(html, settings)

        expected_content = (
            '<img class="test image-process image-process-crop'
            ' test2" src="/tmp/derivatives/crop/test.jpg"/>'
        )

        expected_source = os.path.join(settings["PATH"], "tmp/test.jpg")
        expected_destination = os.path.join(
            settings["OUTPUT_PATH"],
            "tmp",
            settings["IMAGE_PROCESS_DIR"],
            "crop",
            "test.jpg",
        )
        expected_image = (
            expected_source,
            expected_destination,
            ["crop 10 20 100 200"],
        )
        expected_calls = [mock.call(expected_image, settings)]

        self.assertEqual(html, expected_content)
        self.assertEqual(expected_calls, process_image.call_args_list)

    def test_transforms(self):
        settings = get_settings(IMAGE_PROCESS=self.transforms)

        def test_transform(d, i, tmpdir):
            path, name = os.path.split(i)
            destination = os.path.join(tmpdir, d, name)
            image = (i, destination, settings["IMAGE_PROCESS"][d])

            process_image(image, settings)

            transformed = Image.open(destination)

            expected_path = os.path.join(path, "results", d, name)
            expected = Image.open(expected_path)

            img_diff = ImageChops.difference(transformed, expected).getbbox()

            self.assertEqual(img_diff, None)

        with temporary_folder() as tmpdir:
            [
                test_transform(d, i, tmpdir)
                for d in self.transforms
                for i in TEST_IMAGES
            ]


class HTMLGenerationTest(unittest.TestCase):
    """
    Check that all syntaxes generate proper HTML.
    """

    valid_transforms = {
        "thumb": ["crop 0 0 50% 50%", "scale_out 150 150", "crop 0 0 150 150"],
        "article-image": {"type": "image", "ops": ["scale_in 300 300"]},
        "crisp": {
            "type": "responsive-image",
            "srcset": [
                ("1x", ["scale_in 800 600 True"]),
                ("2x", ["scale_in 1600 1200 True"]),
                ("4x", ["scale_in 3200 2400 True"]),
            ],
            "default": "1x",
        },
        "crisp2": {
            "type": "responsive-image",
            "srcset": [
                ("1x", ["scale_in 800 600 True"]),
                ("2x", ["scale_in 1600 1200 True"]),
                ("4x", ["scale_in 3200 2400 True"]),
            ],
            "default": ["scale_in 400 300 True"],
        },
        "large-photo": {
            "type": "responsive-image",
            "sizes": (
                "(min-width: 1200px) 800px, (min-width: 992px) 650px, "
                "(min-width: 768px) 718px, 100vw"
            ),
            "srcset": [
                ("600w", ["scale_in 600 450 True"]),
                ("800w", ["scale_in 800 600 True"]),
                ("1600w", ["scale_in 1600 1200 True"]),
            ],
            "default": "800w",
        },
        "pict": {
            "type": "picture",
            "sources": [
                {
                    "name": "default",
                    "media": "(min-width: 640px)",
                    "srcset": [
                        ("640w", ["scale_in 640 480 True"]),
                        ("1024w", ["scale_in 1024 683 True"]),
                        ("1600w", ["scale_in 1600 1200 True"]),
                    ],
                    "sizes": "100vw",
                },
                {
                    "name": "source-1",
                    "srcset": [
                        ("1x", ["crop 100 100 200 200"]),
                        ("2x", ["crop 100 100 300 300"]),
                    ],
                },
            ],
            "default": ("default", "640w"),
        },
        "pict2": {
            "type": "picture",
            "sources": [
                {
                    "name": "default",
                    "media": "(min-width: 640px)",
                    "srcset": [
                        ("640w", ["scale_in 640 480 True"]),
                        ("1024w", ["scale_in 1024 683 True"]),
                        ("1600w", ["scale_in 1600 1200 True"]),
                    ],
                    "sizes": "100vw",
                },
                {
                    "name": "source-2",
                    "srcset": [
                        ("1x", ["crop 100 100 200 200"]),
                        ("2x", ["crop 100 100 300 300"]),
                    ],
                },
            ],
            "default": ("source-2", ["scale_in 800 600 True"]),
        },
    }

    def test_undefined(self):
        settings = get_settings(IMAGE_PROCESS=self.valid_transforms)
        html = '<img class="image-process-undefined" src="/tmp/test.jpg" />'
        with self.assertRaises(RuntimeError):
            harvest_images_in_fragment(html, settings)

    @mock.patch("pelican_image_process.process_image")
    def test_image_generation(self, process_image):
        settings = get_settings(
            IMAGE_PROCESS=self.valid_transforms, IMAGE_PROCESS_DIR="derivs"
        )

        test_data = [
            (
                '<img class="image-process-thumb" src="/tmp/test.jpg" />',
                '<img class="image-process-thumb" '
                'src="/tmp/derivs/thumb/test.jpg"/>',
                (
                    "tmp/test.jpg",
                    "thumb/test.jpg",
                    [
                        "crop 0 0 50% 50%",
                        "scale_out 150 150",
                        "crop 0 0 150 150",
                    ],
                ),
            ),
            (
                '<img class="image-process-article-image" src="/tmp/test.jpg" />',
                '<img class="image-process-article-image" '
                'src="/tmp/derivs/article-image/test.jpg"/>',
                (
                    "tmp/test.jpg",
                    "article-image/test.jpg",
                    ["scale_in 300 300"],
                ),
            ),
        ]

        for data in test_data:
            expected_source = os.path.join(settings["PATH"], data[2][0])
            expected_destination = os.path.join(
                settings["OUTPUT_PATH"],
                "tmp",
                settings["IMAGE_PROCESS_DIR"],
                data[2][1],
            )
            html = harvest_images_in_fragment(data[0], settings)

            expected_image = (
                expected_source,
                expected_destination,
                data[2][2],
            )

            expected_calls = [mock.call(expected_image, settings)]
            self.assertEqual(html, data[1])
            self.assertEqual(expected_calls, process_image.call_args_list)
            pelican_image_process.process_image.reset_mock()

    @mock.patch("pelican_image_process.process_image")
    def test_responsive_image_generation(self, process_image):
        settings = get_settings(
            IMAGE_PROCESS=self.valid_transforms, IMAGE_PROCESS_DIR="derivs"
        )
        test_data = [
            (
                '<img class="image-process-crisp" src="/tmp/test.jpg" />',
                '<img class="image-process-crisp" '
                'src="/tmp/derivs/crisp/1x/test.jpg" '
                'srcset="/tmp/derivs/crisp/1x/test.jpg 1x, '
                "/tmp/derivs/crisp/2x/test.jpg 2x, "
                '/tmp/derivs/crisp/4x/test.jpg 4x"/>',
                [
                    (
                        "tmp/test.jpg",
                        "crisp/1x/test.jpg",
                        ["scale_in 800 600 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "crisp/2x/test.jpg",
                        ["scale_in 1600 1200 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "crisp/4x/test.jpg",
                        ["scale_in 3200 2400 True"],
                    ),
                ],
            ),
            (
                '<img class="image-process-crisp2" src="/tmp/test.jpg" />',
                '<img class="image-process-crisp2" '
                'src="/tmp/derivs/crisp2/default/test.jpg" '
                'srcset="/tmp/derivs/crisp2/1x/test.jpg 1x, '
                "/tmp/derivs/crisp2/2x/test.jpg 2x, "
                '/tmp/derivs/crisp2/4x/test.jpg 4x"/>',
                # default must be first, because the process execute it first
                [
                    (
                        "tmp/test.jpg",
                        "crisp2/default/test.jpg",
                        ["scale_in 400 300 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "crisp2/1x/test.jpg",
                        ["scale_in 800 600 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "crisp2/2x/test.jpg",
                        ["scale_in 1600 1200 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "crisp2/4x/test.jpg",
                        ["scale_in 3200 2400 True"],
                    ),
                ],
            ),
            (
                '<img class="image-process-large-photo" src="/tmp/test.jpg" />',
                '<img class="image-process-large-photo" '
                'sizes="(min-width: 1200px) 800px, (min-width: 992px) 650px, '
                '(min-width: 768px) 718px, 100vw" src="/tmp/derivs/large-photo/'
                '800w/test.jpg" '
                'srcset="/tmp/derivs/large-photo/600w/test.jpg 600w, '
                "/tmp/derivs/large-photo/800w/test.jpg 800w, "
                '/tmp/derivs/large-photo/1600w/test.jpg 1600w"/>',
                [
                    (
                        "tmp/test.jpg",
                        "large-photo/600w/test.jpg",
                        ["scale_in 600 450 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "large-photo/800w/test.jpg",
                        ["scale_in 800 600 True"],
                    ),
                    (
                        "tmp/test.jpg",
                        "large-photo/1600w/test.jpg",
                        ["scale_in 1600 1200 True"],
                    ),
                ],
            ),
        ]

        for data in test_data:
            html = harvest_images_in_fragment(data[0], settings)

            expected_images = []
            expected_calls = []

            for t in data[2]:
                expected_source = os.path.join(settings["PATH"], t[0])
                expected_destination = os.path.join(
                    settings["OUTPUT_PATH"],
                    "tmp",
                    settings["IMAGE_PROCESS_DIR"],
                    t[1],
                )

                expected_image = (expected_source, expected_destination, t[2])
                expected_images.append(expected_image)
                expected_calls.append(mock.call(expected_image, settings))

            self.maxDiff = None
            self.assertEqual(html, data[1])
            self.assertEqual(process_image.call_args_list, expected_calls)

            pelican_image_process.process_image.reset_mock()

    @mock.patch("pelican_image_process.process_image")
    def test_picture_generation(self, process_image):
        settings = get_settings(
            IMAGE_PROCESS=self.valid_transforms, IMAGE_PROCESS_DIR="derivs"
        )
        test_data = [
            (
                '<picture><source class="source-1" '
                'src="/images/pelican-closeup.jpg"/><img '
                'class="image-process-pict" src="/images/pelican.jpg"/>'
                '</picture>',
                '<picture><source media="(min-width: 640px)" sizes="100vw" '
                'srcset="/images/derivs/pict/default/640w/pelican.jpg 640w, '
                '/images/derivs/pict/default/1024w/pelican.jpg 1024w, '
                '/images/derivs/pict/default/1600w/pelican.jpg 1600w"/>'
                '<source srcset="/images/derivs/pict/source-1/1x/'
                'pelican-closeup.jpg 1x, /images/derivs/pict/source-1/2x/'
                'pelican-closeup.jpg 2x"/><img '
                'class="image-process-pict" '
                'src="/images/derivs/pict/default/640w/pelican.jpg"/>'
                '</picture>',
                [
                    (
                        "images/pelican.jpg",
                        "pict/default/640w/pelican.jpg",
                        ["scale_in 640 480 True"],
                    ),
                    (
                        "images/pelican.jpg",
                        "pict/default/1024w/pelican.jpg",
                        ["scale_in 1024 683 True"],
                    ),
                    (
                        "images/pelican.jpg",
                        "pict/default/1600w/pelican.jpg",
                        ["scale_in 1600 1200 True"],
                    ),
                    (
                        "images/pelican-closeup.jpg",
                        "pict/source-1/1x/pelican-closeup.jpg",
                        ["crop 100 100 200 200"],
                    ),
                    (
                        "images/pelican-closeup.jpg",
                        "pict/source-1/2x/pelican-closeup.jpg",
                        ["crop 100 100 300 300"],
                    ),
                ],
            ),
            (
                '<div class="figure"><img alt="Pelican" class="image-process'
                '-pict2" src="/images/pelican.jpg" /> <p class="caption">'
                'A nice pelican</p> <div class="legend"> <img alt="Other view of '
                'pelican" class="image-process source-2" src="/images/'
                'pelican-closeup.jpg" /></div></div>',
                '<div class="figure"><picture><source media="(min-width: 640px)" '
                'sizes="100vw" srcset="/images/derivs/pict2/default/640w/pelican'
                ".jpg 640w, /images/derivs/pict2/default/1024w/pelican.jpg 1024w,"
                ' /images/derivs/pict2/default/1600w/pelican.jpg 1600w"/>'
                '<source srcset="/images/derivs/pict2/source-2/1x/pelican-closeup'
                ".jpg 1x, /images/derivs/pict2/source-2/2x/pelican-closeup.jpg "
                '2x"/><img alt="Pelican" class="image-process-pict2" '
                'src="/images/derivs/pict2/source-2/default/pelican-closeup.jpg"'
                '/></picture> <p class="caption">A nice pelican</p> <div '
                'class="legend"> </div></div>',
                [
                    # default call first
                    (
                        "images/pelican-closeup.jpg",
                        "pict2/source-2/default/pelican-closeup.jpg",
                        ["scale_in 800 600 True"],
                    ),
                    (
                        "images/pelican.jpg",
                        "pict2/default/640w/pelican.jpg",
                        ["scale_in 640 480 True"],
                    ),
                    # then images in order of processing
                    (
                        "images/pelican.jpg",
                        "pict2/default/1024w/pelican.jpg",
                        ["scale_in 1024 683 True"],
                    ),
                    (
                        "images/pelican.jpg",
                        "pict2/default/1600w/pelican.jpg",
                        ["scale_in 1600 1200 True"],
                    ),
                    (
                        "images/pelican-closeup.jpg",
                        "pict2/source-2/1x/pelican-closeup.jpg",
                        ["crop 100 100 200 200"],
                    ),
                    (
                        "images/pelican-closeup.jpg",
                        "pict2/source-2/2x/pelican-closeup.jpg",
                        ["crop 100 100 300 300"],
                    ),
                ],
            ),
        ]

        for data in test_data:
            html = harvest_images_in_fragment(data[0], settings)

            expected_images = []
            expected_calls = []
            for t in data[2]:
                expected_source = os.path.join(settings["PATH"], t[0])
                expected_destination = os.path.join(
                    settings["OUTPUT_PATH"],
                    "images",
                    settings["IMAGE_PROCESS_DIR"],
                    t[1],
                )

                expected_image = (expected_source, expected_destination, t[2])
                expected_images.append(expected_image)
                expected_calls.append(mock.call(expected_image, settings))

            self.maxDiff = None
            self.assertEqual(html, data[1])
            self.assertEqual(process_image.call_args_list, expected_calls)

            pelican_image_process.process_image.reset_mock()


if __name__ == "__main__":
    unittest.main()
