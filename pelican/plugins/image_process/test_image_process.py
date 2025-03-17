import json
import os
from pathlib import Path
import shutil
import subprocess
import warnings

from PIL import Image, UnidentifiedImageError
import pytest

from pelican.plugins.image_process import (
    ExifTool,
    compute_paths,
    harvest_images_in_fragment,
    process_image,
    set_default_settings,
    try_open_image,
)

# Prepare test image constants.
HERE = Path(__file__).resolve().parent
TEST_DATA = HERE.joinpath("test_data").resolve()

SUPPORTED_TRANSPARENT_IMAGE_FORMATS = ["png", "webp"]
SUPPORTED_IMAGE_FORMATS = [*SUPPORTED_TRANSPARENT_IMAGE_FORMATS, "jpg"]
SUPPORTED_EXIF_IMAGE_FORMATS = ["png", "jpg"]  # Exiftool cannot write webp images.

TRANSFORM_TEST_IMAGES = [
    TEST_DATA.joinpath(f"{file}.png").resolve()
    for file in ["pelican-bird", "black-borders", "alpha-borders"]
]
FILE_FORMAT_TEST_IMAGES = [
    TEST_DATA.joinpath(f"pelican-bird.{ext}").resolve()
    for ext in SUPPORTED_IMAGE_FORMATS
]
FILE_FORMAT_TEST_IMAGES = FILE_FORMAT_TEST_IMAGES + [
    TEST_DATA.joinpath(f"alpha-borders.{ext}").resolve()
    for ext in SUPPORTED_TRANSPARENT_IMAGE_FORMATS
]
EXIF_TEST_IMAGES = [
    TEST_DATA.joinpath("exif", f"pelican-bird.{ext}").resolve()
    for ext in SUPPORTED_EXIF_IMAGE_FORMATS
]
TRANSFORM_RESULTS = TEST_DATA.joinpath("results").resolve()

# Register all supported transforms.
SINGLE_TRANSFORMS = {
    "crop": ["crop 350 250 650 450"],
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

# The expected sizes of the transformed images.
EXPECTED_SIZES = {
    "crop": (300, 200),
    "resize": (200, 250),
    "rotate": (1226, 1072),
    "scale_in": (200, 150),
    "scale_out": (333, 250),
}


def get_settings(**kwargs):
    """Provide tweaked setting dictionaries for testing.

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
    set_default_settings(settings)
    return settings


def test_undefined_transform():
    settings = get_settings()
    tag = "<img class='image-process-undefined' src='/tmp/test.jpg' />"
    with pytest.raises(RuntimeError):
        harvest_images_in_fragment(tag, settings)


@pytest.mark.parametrize("transform_id, transform_params", SINGLE_TRANSFORMS.items())
@pytest.mark.parametrize("image_path", TRANSFORM_TEST_IMAGES)
def test_all_transforms(tmp_path, transform_id, transform_params, image_path):
    """Test the raw transform and their results on images."""
    settings = get_settings()

    image_name = image_path.name
    destination_path = tmp_path.joinpath(transform_id, image_name)
    expected_path = TRANSFORM_RESULTS.joinpath(transform_id, image_name)

    process_image((str(image_path), str(destination_path), transform_params), settings)

    transformed = Image.open(destination_path)
    expected = Image.open(expected_path)

    assert transformed.size == expected.size

    # We need to make our tests slightly tolerant because
    # the `detail` and `smooth_more` filters are slightly different in Pillow 10.3+
    # depending on the platform on which they are run.
    if transformed.mode == "RGB":
        for _, (transformed_pixel, expected_pixel) in enumerate(
            zip(transformed.getdata(), expected.getdata())
        ):
            assert abs(transformed_pixel[0] - expected_pixel[0]) <= 1
            assert abs(transformed_pixel[1] - expected_pixel[1]) <= 1
            assert abs(transformed_pixel[2] - expected_pixel[2]) <= 1
    elif transformed.mode == "RGBA":
        for _, (transformed_pixel, expected_pixel) in enumerate(
            zip(transformed.getdata(), expected.getdata())
        ):
            assert abs(transformed_pixel[0] - expected_pixel[0]) <= 1
            assert abs(transformed_pixel[1] - expected_pixel[1]) <= 1
            assert abs(transformed_pixel[2] - expected_pixel[2]) <= 1
            assert abs(transformed_pixel[3] - expected_pixel[3]) <= 1
    elif transformed.mode == "L":
        for _, (transformed_pixel, expected_pixel) in enumerate(
            zip(transformed.getdata(), expected.getdata())
        ):
            assert abs(transformed_pixel - expected_pixel) <= 1
    else:
        raise ValueError(f"Unsupported image mode: {transformed.mode}")


@pytest.mark.parametrize("image_path", FILE_FORMAT_TEST_IMAGES)
def test_image_formats(tmp_path, image_path):
    """Test that we can process images in various formats."""
    settings = get_settings()

    output_ext = image_path.suffix.lower()
    destination_path = tmp_path.joinpath(f"processed.{output_ext}")

    process_image((str(image_path), str(destination_path), []), settings)

    original = Image.open(image_path)
    transformed = Image.open(destination_path)

    assert transformed.size == original.size


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
        f'<img class="test image-process image-process-crop test2" src="{orig_src}"/>'
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
def test_html_and_pictures_generation(mocker, orig_tag, new_tag, call_args):
    """Tests that the generated html is as expected and the images are processed."""
    process = mocker.patch("pelican.plugins.image_process.image_process.process_image")

    settings = get_settings(
        IMAGE_PROCESS=COMPLEX_TRANSFORMS, IMAGE_PROCESS_DIR="derivs"
    )

    assert harvest_images_in_fragment(orig_tag, settings) == new_tag

    # Check that process_image was called with the expected arguments
    # and in the expecter order.
    for i, (orig_img, new_img, transform_params) in enumerate(call_args):
        assert process.mock_calls[i] == mocker.call(
            (
                os.path.join(settings["PATH"], orig_img),
                os.path.join(settings["OUTPUT_PATH"], new_img),
                transform_params,
            ),
            settings,
        )


@pytest.mark.parametrize(
    "orig_tag, new_tag",
    [
        # <img/> src attribute with no quotes, spaces or commas.
        (
            '<img class="image-process-thumb" src="/tmp/my&amp;_dir/my!_test.jpg" />',
            '<img class="image-process-thumb" '
            'src="/tmp/my&amp;_dir/derivs/thumb/my!_test.jpg"/>',
        ),
        # <img/> src attribute with double quotes, spaces and commas.
        (
            '<img class="image-process-thumb" '
            'src="/tmp/my,&quot; dir/my &#34;test,.jpg" />',
            '<img class="image-process-thumb" '
            "src='/tmp/my,\" dir/derivs/thumb/my \"test,.jpg'/>",
        ),
        # <img/> src attribute with single and double quotes, spaces and commas.
        (
            '<img class="image-process-thumb" '
            'src="/tmp/m\'y,&quot; dir/my &#34;test,.jpg" />',
            '<img class="image-process-thumb" '
            'src="/tmp/m\'y,&quot; dir/derivs/thumb/my &quot;test,.jpg"/>',
        ),
        # <img/> srcset attribute with no quotes, spaces or commas.
        (
            '<img class="image-process-crisp" src="/tmp/my&amp;_dir/my!_test.jpg" />',
            '<img class="image-process-crisp" '
            'src="/tmp/my&amp;_dir/derivs/crisp/1x/my!_test.jpg" '
            'srcset="/tmp/my&amp;_dir/derivs/crisp/1x/my!_test.jpg 1x, '
            "/tmp/my&amp;_dir/derivs/crisp/2x/my!_test.jpg 2x, "
            '/tmp/my&amp;_dir/derivs/crisp/4x/my!_test.jpg 4x"/>',
        ),
        # <img/> srcset attribute with double quotes, spaces and commas.
        (
            '<img class="image-process-crisp" '
            'src="/tmp/my,&quot; dir/my &#34;test,.jpg" />',
            '<img class="image-process-crisp" '
            "src='/tmp/my,\" dir/derivs/crisp/1x/my \"test,.jpg' "
            'srcset="/tmp/my%2C%22%20dir/derivs/crisp/1x/my%20%22test%2C.jpg 1x, '
            "/tmp/my%2C%22%20dir/derivs/crisp/2x/my%20%22test%2C.jpg 2x, "
            '/tmp/my%2C%22%20dir/derivs/crisp/4x/my%20%22test%2C.jpg 4x"/>',
        ),
        # <img/> srcset attribute with single and double quotes, spaces and commas.
        (
            '<img class="image-process-crisp" '
            'src="/tmp/m\'y,&quot; dir/my &#34;test,.jpg" />',
            '<img class="image-process-crisp" '
            'src="/tmp/m\'y,&quot; dir/derivs/crisp/1x/my &quot;test,.jpg" '
            'srcset="/tmp/m%27y%2C%22%20dir/derivs/crisp/1x/my%20%22test%2C.jpg 1x, '
            "/tmp/m%27y%2C%22%20dir/derivs/crisp/2x/my%20%22test%2C.jpg 2x, "
            '/tmp/m%27y%2C%22%20dir/derivs/crisp/4x/my%20%22test%2C.jpg 4x"/>',
        ),
        # <picture/> src and srcset attributes with no quotes, spaces or commas.
        (
            '<picture><source class="source-1" '
            'src="/my&amp;_dir/my!_pelican-closeup.jpg"/><img '
            'class="image-process-pict" src="/my&amp;_dir/my!_pelican.jpg"/>'
            "</picture>",
            '<picture><source media="(min-width: 640px)" sizes="100vw" '
            'srcset="/my&amp;_dir/derivs/pict/default/640w/'
            "my!_pelican.jpg 640w, "
            "/my&amp;_dir/derivs/pict/default/1024w/my!_pelican.jpg 1024w, "
            '/my&amp;_dir/derivs/pict/default/1600w/my!_pelican.jpg 1600w"/>'
            '<source srcset="/my&amp;_dir/derivs/pict/source-1/1x/'
            "my!_pelican-closeup.jpg 1x, "
            "/my&amp;_dir/derivs/pict/source-1/2x/"
            'my!_pelican-closeup.jpg 2x"/><img '
            'class="image-process-pict" '
            'src="/my&amp;_dir/derivs/pict/default/640w/my!_pelican.jpg"/>'
            "</picture>",
        ),
        # <picture/> src and srcset attributes with double quotes, spaces and commas.
        (
            '<picture><source class="source-1" '
            'src="/my,&quot; dir/my &#34;pelican-closeup,.jpg"/><img '
            'class="image-process-pict" src="/my,&quot; dir/my &#34;pelican,.jpg"/>'
            "</picture>",
            '<picture><source media="(min-width: 640px)" sizes="100vw" '
            'srcset="/my%2C%22%20dir/derivs/pict/default/640w/'
            "my%20%22pelican%2C.jpg 640w, "
            "/my%2C%22%20dir/derivs/pict/default/1024w/my%20%22pelican%2C.jpg 1024w, "
            '/my%2C%22%20dir/derivs/pict/default/1600w/my%20%22pelican%2C.jpg 1600w"/>'
            '<source srcset="/my%2C%22%20dir/derivs/pict/source-1/1x/'
            "my%20%22pelican-closeup%2C.jpg 1x, "
            "/my%2C%22%20dir/derivs/pict/source-1/2x/"
            'my%20%22pelican-closeup%2C.jpg 2x"/><img '
            'class="image-process-pict" '
            "src='/my,\" dir/derivs/pict/default/640w/my \"pelican,.jpg'/>"
            "</picture>",
        ),
        # <picture/> src and srcset attributes
        # with single and double quotes, spaces and commas.
        (
            '<picture><source class="source-1" '
            'src="/m\'y,&quot; dir/my &#34;pelican-closeup,.jpg"/><img '
            'class="image-process-pict" src="/m\'y,&quot; dir/my &#34;pelican,.jpg"/>'
            "</picture>",
            '<picture><source media="(min-width: 640px)" sizes="100vw" '
            'srcset="/m%27y%2C%22%20dir/derivs/pict/default/640w/'
            "my%20%22pelican%2C.jpg 640w, "
            "/m%27y%2C%22%20dir/derivs/pict/default/1024w/"
            "my%20%22pelican%2C.jpg 1024w, "
            "/m%27y%2C%22%20dir/derivs/pict/default/1600w/"
            'my%20%22pelican%2C.jpg 1600w"/>'
            '<source srcset="/m%27y%2C%22%20dir/derivs/pict/source-1/1x/'
            "my%20%22pelican-closeup%2C.jpg 1x, "
            "/m%27y%2C%22%20dir/derivs/pict/source-1/2x/"
            'my%20%22pelican-closeup%2C.jpg 2x"/><img '
            'class="image-process-pict" '
            'src="/m\'y,&quot; dir/derivs/pict/default/640w/my &quot;pelican,.jpg"/>'
            "</picture>",
        ),
    ],
)
def test_special_chars_in_image_path_are_handled_properly(mocker, orig_tag, new_tag):
    """Tests that special characters in image paths are handled properly.

    For the src attribute, single or double quotes may need to be escaped,
    according to the quotation mark used to enclose the attribute value.

    For the srcset attribute, in addition to quotes, spaces and commas
    need to be url-encoded.

    Related to issue #78 https://github.com/pelican-plugins/image-process/issues/78
    """
    mocker.patch("pelican.plugins.image_process.image_process.process_image")

    settings = get_settings(
        IMAGE_PROCESS=COMPLEX_TRANSFORMS, IMAGE_PROCESS_DIR="derivs"
    )

    assert harvest_images_in_fragment(orig_tag, settings) == new_tag


def process_image_mock_exif_tool_started(image, settings):
    assert ExifTool._instance is not None


def process_image_mock_exif_tool_not_started(image, settings):
    assert ExifTool._instance is None


@pytest.mark.parametrize("copy_tags", [True, False])
def test_exiftool_process_is_started_only_when_necessary(mocker, copy_tags):
    if shutil.which("exiftool") is None:
        warnings.warn(
            "EXIF tags copying will not be tested because the exiftool program could "
            "not be found. Please install exiftool and make sure it is in your path.",
            stacklevel=2,
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
            "not be found. Please install exiftool and make sure it is in your path.",
            stacklevel=2,
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
        ["exiftool", "-json", image_path], stdout=subprocess.PIPE, check=False
    )
    expected_tags = json.loads(expected_results.stdout)[0]
    for tag in exif_tags:
        assert tag in expected_tags

    if copy_tags:
        ExifTool.start_exiftool()
    process_image((str(image_path), str(destination_path), transform_params), settings)
    if copy_tags:
        ExifTool.stop_exiftool()

    actual_results = subprocess.run(
        ["exiftool", "-json", destination_path], stdout=subprocess.PIPE, check=False
    )

    assert actual_results.returncode == 0

    actual_tags = json.loads(actual_results.stdout)[0]
    for tag in exif_tags:
        if copy_tags:
            assert tag in actual_tags
            assert expected_tags[tag] == actual_tags[tag]
        else:
            assert tag not in actual_tags


def test_try_open_image():
    for test_image in FILE_FORMAT_TEST_IMAGES:
        assert try_open_image(test_image)

    with pytest.raises(FileNotFoundError):
        try_open_image("image/that/does/not/exist.png")

    with pytest.raises(UnidentifiedImageError):
        assert not try_open_image(TEST_DATA.joinpath("folded_puzzle.png"))
        assert not try_open_image(TEST_DATA.joinpath("minimal.svg"))

    img = {"src": "https://upload.wikimedia.org/wikipedia/commons/3/34/Exemple.png"}
    settings = get_settings(IMAGE_PROCESS_DIR="derivatives")
    path = compute_paths(img, settings, derivative="thumb")
    with pytest.raises(FileNotFoundError):
        assert not try_open_image(path.source)


@pytest.mark.parametrize(
    "orig_tag, new_tag, setting_overrides",
    [
        (
            '<img class="image-process-crop" src="/tmp/test.jpg" />',
            '<img class="image-process-crop" src="/tmp/derivatives/crop/test.jpg"/>',
            [  # Default settings.
                {},
                {"IMAGE_PROCESS_ADD_CLASS": True},
                {"IMAGE_PROCESS_CLASS_PREFIX": "image-process-"},
                {
                    "IMAGE_PROCESS_ADD_CLASS": True,
                    "IMAGE_PROCESS_CLASS_PREFIX": "image-process-",
                },
            ],
        ),
        (
            '<img class="image-process-crop" src="/tmp/test.jpg" />',
            '<img class="custom-prefix-crop" src="/tmp/derivatives/crop/test.jpg"/>',
            [  # Custom class prefix.
                {"IMAGE_PROCESS_CLASS_PREFIX": "custom-prefix-"},
                {
                    "IMAGE_PROCESS_ADD_CLASS": True,
                    "IMAGE_PROCESS_CLASS_PREFIX": "custom-prefix-",
                },
            ],
        ),
        (
            '<img class="image-process-crop" src="/tmp/test.jpg" />',
            '<img class="crop" src="/tmp/derivatives/crop/test.jpg"/>',
            [  # Special case: empty string as class prefix.
                {"IMAGE_PROCESS_CLASS_PREFIX": ""},
            ],
        ),
        (
            '<img class="image-process-crop" src="/tmp/test.jpg" />',
            '<img src="/tmp/derivatives/crop/test.jpg"/>',
            [  # No class added.
                {"IMAGE_PROCESS_ADD_CLASS": False},
                {"IMAGE_PROCESS_ADD_CLASS": False, "IMAGE_PROCESS_CLASS_PREFIX": ""},
            ],
        ),
    ],
)
def test_class_settings(mocker, orig_tag, new_tag, setting_overrides):
    """Test the IMAGE_PROCESS_ADD_CLASS and IMAGE_PROCESS_CLASS_PREFIX settings."""
    # Silence image transforms.
    mocker.patch("pelican.plugins.image_process.image_process.process_image")

    for override in setting_overrides:
        settings = get_settings(**override)
        assert harvest_images_in_fragment(orig_tag, settings) == new_tag


def generate_test_images():
    settings = get_settings()
    image_count = 0
    for image_path in TRANSFORM_TEST_IMAGES:
        for transform_id, transform_params in SINGLE_TRANSFORMS.items():
            destination_path = str(
                TRANSFORM_RESULTS.joinpath(transform_id, image_path.name)
            )
            process_image(
                (
                    str(image_path),
                    destination_path,
                    transform_params,
                ),
                settings,
            )
            image_count += 1

            # Check the size of the transformed image.
            expected_size = EXPECTED_SIZES.get(transform_id)
            transformed = Image.open(destination_path)
            assert expected_size is None or expected_size == transformed.size

    print(f"{image_count} test images generated!")  # noqa: T201
