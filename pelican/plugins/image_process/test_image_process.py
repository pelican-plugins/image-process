import json
import os
from pathlib import Path
import shutil
import subprocess
import warnings

from PIL import Image, ImageChops
import pytest

from pelican.plugins.image_process import (
    ExifTool,
    harvest_images_in_fragment,
    process_image,
)

# Prepare test image constants.
HERE = Path(__file__).resolve().parent
TEST_DATA = HERE.joinpath("test_data").resolve()
TEST_IMAGES = [
    TEST_DATA.joinpath(f"pelican-bird.{ext}").resolve() for ext in ["jpg", "png"]
]
EXIF_TEST_IMAGES = [
    TEST_DATA.joinpath("exif", f"pelican-bird.{ext}").resolve()
    for ext in ["jpg", "png"]
]
TRANSFORM_RESULTS = TEST_DATA.joinpath("results").resolve()

# Register all supported transforms.
SINGLE_TRANSFORMS = {
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


def get_settings(**kwargs):
    """Provide tweaked setting dictionaries for testing
    Set keyword arguments to override specific settings.
    """
    DEFAULT_CONFIG = {
        "PATH": HERE,
        "OUTPUT_PATH": "output",
        "static_content": {},
        "filenames": {},
        "SITEURL": "//",
        "IMAGE_PROCESS": SINGLE_TRANSFORMS,
    }
    settings = DEFAULT_CONFIG.copy()
    settings.update(kwargs)
    return settings


def test_undefined_transform():
    settings = get_settings()
    tag = "<img class='image-process-undefined' src='/tmp/test.jpg' />"
    with pytest.raises(RuntimeError):
        harvest_images_in_fragment(tag, settings)


@pytest.mark.parametrize("transform_id, transform_params", SINGLE_TRANSFORMS.items())
@pytest.mark.parametrize("image_path", TEST_IMAGES)
def test_all_transforms(tmp_path, transform_id, transform_params, image_path):
    """Test the raw transform and their results on images."""
    settings = get_settings()

    image_name = image_path.name
    destination_path = tmp_path.joinpath(transform_id, image_name)
    expected_path = TRANSFORM_RESULTS.joinpath(transform_id, image_name)

    process_image((str(image_path), str(destination_path), transform_params), settings)

    transformed = Image.open(destination_path)
    expected = Image.open(expected_path)
    image_diff = ImageChops.difference(transformed, expected).getbbox()
    assert image_diff is None


@pytest.mark.parametrize(
    "orig_src, orig_img, new_src, new_img",
    [
        (
            "/tmp/test.jpg",
            "tmp/test.jpg",
            "/tmp/derivatives/crop/test.jpg",
            "tmp/derivatives/crop/test.jpg",
        ),
        (
            "../tmp/test.jpg",
            "../tmp/test.jpg",
            "../tmp/derivatives/crop/test.jpg",
            "../tmp/derivatives/crop/test.jpg",
        ),
        (
            "http://xxx/tmp/test.jpg",
            "tmp/test.jpg",
            "http://xxx/tmp/derivatives/crop/test.jpg",
            "tmp/derivatives/crop/test.jpg",
        ),
    ],
)
def test_path_normalization(mocker, orig_src, orig_img, new_src, new_img):
    # Silence image transforms.
    process = mocker.patch("pelican.plugins.image_process.image_process.process_image")

    settings = get_settings(IMAGE_PROCESS_DIR="derivatives")

    img_tag_orig = (
        '<img class="test image-process image-process-crop test2" '
        f'src="{orig_src}"/>'
    )

    img_tag_processed = harvest_images_in_fragment(img_tag_orig, settings)

    assert img_tag_processed == (
        f'<img class="test image-process image-process-crop test2" src="{new_src}"/>'
    )

    process.assert_called_once_with(
        (
            os.path.join(settings["PATH"], orig_img),
            os.path.join(settings["OUTPUT_PATH"], new_img),
            SINGLE_TRANSFORMS["crop"],
        ),
        settings,
    )


COMPLEX_TRANSFORMS = {
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
            "(min-width: 1200px) 800px, "
            "(min-width: 992px) 650px, "
            "(min-width: 768px) 718px, "
            "100vw"
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


@pytest.mark.parametrize(
    "orig_tag, new_tag, call_args",
    [
        (
            '<img class="image-process-thumb" src="/tmp/test.jpg" />',
            '<img class="image-process-thumb" src="/tmp/derivs/thumb/test.jpg"/>',
            [
                (
                    "tmp/test.jpg",
                    "tmp/derivs/thumb/test.jpg",
                    ["crop 0 0 50% 50%", "scale_out 150 150", "crop 0 0 150 150"],
                ),
            ],
        ),
        (
            '<img class="image-process-article-image" src="/tmp/test.jpg" />',
            '<img class="image-process-article-image" '
            'src="/tmp/derivs/article-image/test.jpg"/>',
            [
                (
                    "tmp/test.jpg",
                    "tmp/derivs/article-image/test.jpg",
                    ["scale_in 300 300"],
                ),
            ],
        ),
        (
            '<img class="image-process-crisp" src="/tmp/test.jpg" />',
            '<img class="image-process-crisp" src="/tmp/derivs/crisp/1x/test.jpg" '
            'srcset="/tmp/derivs/crisp/1x/test.jpg 1x, '
            "/tmp/derivs/crisp/2x/test.jpg 2x, "
            '/tmp/derivs/crisp/4x/test.jpg 4x"/>',
            [
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp/1x/test.jpg",
                    ["scale_in 800 600 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp/2x/test.jpg",
                    ["scale_in 1600 1200 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp/4x/test.jpg",
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
                    "tmp/derivs/crisp2/default/test.jpg",
                    ["scale_in 400 300 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp2/1x/test.jpg",
                    ["scale_in 800 600 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp2/2x/test.jpg",
                    ["scale_in 1600 1200 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/crisp2/4x/test.jpg",
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
                    "tmp/derivs/large-photo/600w/test.jpg",
                    ["scale_in 600 450 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/large-photo/800w/test.jpg",
                    ["scale_in 800 600 True"],
                ),
                (
                    "tmp/test.jpg",
                    "tmp/derivs/large-photo/1600w/test.jpg",
                    ["scale_in 1600 1200 True"],
                ),
            ],
        ),
        (
            '<picture><source class="source-1" '
            'src="/images/pelican-closeup.jpg"/><img '
            'class="image-process-pict" src="/images/pelican.jpg"/>'
            "</picture>",
            '<picture><source media="(min-width: 640px)" sizes="100vw" '
            'srcset="/images/derivs/pict/default/640w/pelican.jpg 640w, '
            "/images/derivs/pict/default/1024w/pelican.jpg 1024w, "
            '/images/derivs/pict/default/1600w/pelican.jpg 1600w"/>'
            '<source srcset="/images/derivs/pict/source-1/1x/'
            "pelican-closeup.jpg 1x, /images/derivs/pict/source-1/2x/"
            'pelican-closeup.jpg 2x"/><img '
            'class="image-process-pict" '
            'src="/images/derivs/pict/default/640w/pelican.jpg"/>'
            "</picture>",
            [
                (
                    "images/pelican.jpg",
                    "images/derivs/pict/default/640w/pelican.jpg",
                    ["scale_in 640 480 True"],
                ),
                (
                    "images/pelican.jpg",
                    "images/derivs/pict/default/1024w/pelican.jpg",
                    ["scale_in 1024 683 True"],
                ),
                (
                    "images/pelican.jpg",
                    "images/derivs/pict/default/1600w/pelican.jpg",
                    ["scale_in 1600 1200 True"],
                ),
                (
                    "images/pelican-closeup.jpg",
                    "images/derivs/pict/source-1/1x/pelican-closeup.jpg",
                    ["crop 100 100 200 200"],
                ),
                (
                    "images/pelican-closeup.jpg",
                    "images/derivs/pict/source-1/2x/pelican-closeup.jpg",
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
                # Default calls first.
                (
                    "images/pelican-closeup.jpg",
                    "images/derivs/pict2/source-2/default/pelican-closeup.jpg",
                    ["scale_in 800 600 True"],
                ),
                (
                    "images/pelican.jpg",
                    "images/derivs/pict2/default/640w/pelican.jpg",
                    ["scale_in 640 480 True"],
                ),
                # Then images in processing order.
                (
                    "images/pelican.jpg",
                    "images/derivs/pict2/default/1024w/pelican.jpg",
                    ["scale_in 1024 683 True"],
                ),
                (
                    "images/pelican.jpg",
                    "images/derivs/pict2/default/1600w/pelican.jpg",
                    ["scale_in 1600 1200 True"],
                ),
                (
                    "images/pelican-closeup.jpg",
                    "images/derivs/pict2/source-2/1x/pelican-closeup.jpg",
                    ["crop 100 100 200 200"],
                ),
                (
                    "images/pelican-closeup.jpg",
                    "images/derivs/pict2/source-2/2x/pelican-closeup.jpg",
                    ["crop 100 100 300 300"],
                ),
            ],
        ),
    ],
)
def test_picture_generation(mocker, orig_tag, new_tag, call_args):
    process = mocker.patch("pelican.plugins.image_process.image_process.process_image")

    settings = get_settings(
        IMAGE_PROCESS=COMPLEX_TRANSFORMS, IMAGE_PROCESS_DIR="derivs"
    )

    assert harvest_images_in_fragment(orig_tag, settings) == new_tag

    for i, (orig_img, new_img, transform_params) in enumerate(call_args):
        assert process.mock_calls[i] == mocker.call(
            (
                os.path.join(settings["PATH"], orig_img),
                os.path.join(settings["OUTPUT_PATH"], new_img),
                transform_params,
            ),
            settings,
        )


def process_image_mock_exif_tool_started(image, settings):
    assert ExifTool._instance is not None


def process_image_mock_exif_tool_not_started(image, settings):
    assert ExifTool._instance is None


@pytest.mark.parametrize("copy_tags", [True, False])
def test_exiftool_process_is_started_only_when_necessary(mocker, copy_tags):
    if shutil.which("exiftool") is None:
        warnings.warn(
            "EXIF tags copying will not be tested because the exiftool program could "
            "not be found. Please install exiftool and make sure it is in your path."
        )
        return

    if copy_tags:
        mocker.patch(
            "pelican.plugins.image_process.image_process.process_image",
            process_image_mock_exif_tool_started,
        )
    else:
        mocker.patch(
            "pelican.plugins.image_process.image_process.process_image",
            process_image_mock_exif_tool_not_started,
        )

    settings = get_settings(
        IMAGE_PROCESS_COPY_EXIF_TAGS=copy_tags,
        IMAGE_PROCESS=COMPLEX_TRANSFORMS,
        IMAGE_PROCESS_DIR="derivs",
    )

    harvest_images_in_fragment(
        '<img class="image-process-thumb" src="/tmp/test.jpg" />', settings
    )


@pytest.mark.parametrize("image_path", EXIF_TEST_IMAGES)
@pytest.mark.parametrize("copy_tags", [True, False])
def test_copy_exif_tags(tmp_path, image_path, copy_tags):
    if shutil.which("exiftool") is None:
        warnings.warn(
            "EXIF tags copying will not be tested because the exiftool program could "
            "not be found. Please install exiftool and make sure it is in your path."
        )
        return

    # A few EXIF tags to test for.
    exif_tags = [
        "Artist",
        "Creator",
        "Title",
        "Description",
        "Subject",
        "Rating",
        "ExifImageWidth",
    ]

    settings = get_settings(IMAGE_PROCESS_COPY_EXIF_TAGS=copy_tags)

    transform_id = "grayscale"
    transform_params = ["grayscale"]
    image_name = image_path.name
    destination_path = tmp_path.joinpath(transform_id, image_name)

    expected_results = subprocess.run(
        ["exiftool", "-json", image_path], stdout=subprocess.PIPE
    )
    expected_tags = json.loads(expected_results.stdout)[0]
    for tag in exif_tags:
        assert tag in expected_tags.keys()

    if copy_tags:
        ExifTool.start_exiftool()
    process_image((str(image_path), str(destination_path), transform_params), settings)
    if copy_tags:
        ExifTool.stop_exiftool()

    actual_results = subprocess.run(
        ["exiftool", "-json", destination_path], stdout=subprocess.PIPE
    )

    assert actual_results.returncode == 0

    actual_tags = json.loads(actual_results.stdout)[0]
    for tag in exif_tags:
        if copy_tags:
            assert tag in actual_tags.keys()
            assert expected_tags[tag] == actual_tags[tag]
        else:
            assert tag not in actual_tags.keys()
