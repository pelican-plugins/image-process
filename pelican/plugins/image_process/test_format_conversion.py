from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image
import pytest

from pelican.plugins.image_process import (
    harvest_images_in_fragment,
    process_metadata,
    set_default_settings,
)

HERE = Path(__file__).resolve().parent
TEST_DATA = HERE.joinpath("test_data").resolve()


def get_settings(**kwargs):
    DEFAULT_CONFIG = {
        "PATH": str(TEST_DATA),
        "OUTPUT_PATH": "output",
        "static_content": {},
        "filenames": {},
        "SITEURL": "https://www.example.com",
        "IMAGE_PROCESS": {},
    }
    settings = DEFAULT_CONFIG.copy()
    settings.update(kwargs)
    set_default_settings(settings)
    return settings


@pytest.fixture
def output_dir(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return out


def test_single_image_conversion(output_dir):
    settings = get_settings(
        OUTPUT_PATH=str(output_dir),
        IMAGE_PROCESS={
            "webp": {
                "type": "image",
                "ops": ["scale_in 100 100 True"],
                "output-format": "webp",
            }
        },
    )

    fragment = '<img class="image-process-webp" src="/pelican-bird.png">'
    result = harvest_images_in_fragment(fragment, settings)

    soup = BeautifulSoup(result, "html.parser")
    img = soup.find("img")

    assert img["src"] == "/derivatives/webp/pelican-bird.webp"

    dest_path = output_dir / "derivatives" / "webp" / "pelican-bird.webp"
    assert dest_path.exists()

    with Image.open(dest_path) as im:
        assert im.format == "WEBP"


def test_responsive_image_conversion(output_dir):
    settings = get_settings(
        OUTPUT_PATH=str(output_dir),
        IMAGE_PROCESS={
            "responsive": {
                "type": "responsive-image",
                "srcset": [
                    ("small", ["scale_in 100 100 True"], "webp"),
                    (
                        "large",
                        ["scale_in 800 800 True"],
                    ),  # uses top-level default or original
                ],
                "default": "small",
                "output-format": "jpg",
            }
        },
    )

    fragment = '<img class="image-process-responsive" src="/pelican-bird.png">'
    result = harvest_images_in_fragment(fragment, settings)

    soup = BeautifulSoup(result, "html.parser")
    img = soup.find("img")

    assert img["src"] == "/derivatives/responsive/small/pelican-bird.webp"
    assert "srcset" in img.attrs
    srcset = img["srcset"]
    assert "/derivatives/responsive/small/pelican-bird.webp small" in srcset
    assert "/derivatives/responsive/large/pelican-bird.jpg large" in srcset

    assert (
        output_dir / "derivatives" / "responsive" / "small" / "pelican-bird.webp"
    ).exists()
    assert (
        output_dir / "derivatives" / "responsive" / "large" / "pelican-bird.jpg"
    ).exists()


def test_picture_conversion(output_dir):
    settings = get_settings(
        OUTPUT_PATH=str(output_dir),
        IMAGE_PROCESS={
            "viz": {
                "type": "picture",
                "sources": [
                    {
                        "name": "default",
                        "srcset": [("small", ["scale_in 100 100 True"], "webp")],
                    },
                    {
                        "name": "source-1",
                        "srcset": [("large", ["scale_in 800 800 True"], "jpg")],
                    },
                ],
                "default": ("default", "small"),
            }
        },
    )

    fragment = """
    <div>
        <img class="source-1 image-process" src="/black-borders.png">
        <img class="image-process-viz" src="/pelican-bird.png">
    </div>
    """
    result = harvest_images_in_fragment(fragment, settings)

    soup = BeautifulSoup(result, "html.parser")
    picture = soup.find("picture")
    assert picture is not None

    sources = picture.find_all("source")
    assert "webp" in sources[0]["srcset"]
    assert "jpg" in sources[1]["srcset"]

    assert "/derivatives/viz/default/small/pelican-bird.webp" in sources[0]["srcset"]
    assert "/derivatives/viz/source-1/large/black-borders.jpg" in sources[1]["srcset"]

    img = picture.find("img")
    assert img["src"] == "/derivatives/viz/default/small/pelican-bird.webp"


def test_metadata_conversion(output_dir):
    settings = get_settings(
        OUTPUT_PATH=str(output_dir),
        IMAGE_PROCESS={
            "webp-meta": {
                "type": "image",
                "ops": ["scale_in 100 100 True"],
                "output-format": "webp",
            }
        },
        IMAGE_PROCESS_METADATA={"og_image": "webp-meta"},
    )

    class MockGenerator:
        def __init__(self, context):
            self.context = context

    generator = MockGenerator(settings)
    metadata = {"og_image": "/pelican-bird.png"}

    process_metadata(generator, metadata)

    assert (
        metadata["og_image"]
        == "https://www.example.com/derivatives/webp-meta/pelican-bird.webp"
    )
    assert (output_dir / "derivatives" / "webp-meta" / "pelican-bird.webp").exists()


def test_backward_compatibility(output_dir):
    # Ensure that without output-format, it keeps the original extension
    settings = get_settings(
        OUTPUT_PATH=str(output_dir), IMAGE_PROCESS={"legacy": ["scale_in 100 100 True"]}
    )

    fragment = '<img class="image-process-legacy" src="/pelican-bird.png">'
    result = harvest_images_in_fragment(fragment, settings)

    soup = BeautifulSoup(result, "html.parser")
    img = soup.find("img")

    assert img["src"] == "/derivatives/legacy/pelican-bird.png"
    assert (output_dir / "derivatives" / "legacy" / "pelican-bird.png").exists()
