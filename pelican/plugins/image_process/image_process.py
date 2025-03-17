"""Image Process plugin for Pelican.

This plugin processes images according to their class attributes.
"""

import codecs
import collections
import contextlib
import copy
import functools
import html
import logging
import os.path
import posixpath
import pprint
import re
import shutil
import subprocess
import sys
import urllib
from urllib.parse import unquote, urlparse
from urllib.request import pathname2url, url2pathname

from bs4 import BeautifulSoup
from PIL import Image, ImageFilter, UnidentifiedImageError

from pelican import __version__ as pelican_version, signals

logger = logging.getLogger(__name__)

LOG_PREFIX = "[image_process]"

IMAGE_PROCESS_REGEX = re.compile("image-process-[-a-zA-Z0-9_]+")

Path = collections.namedtuple("Path", ["base_url", "source", "base_path", "filename"])


# A lot of inspiration from pyexiftool (https://github.com/smarnach/pyexiftool)
class ExifTool:
    """Class to manage EXIF tags via exiftool."""

    errors = "strict"
    sentinel = b"{ready}"
    block_size = 4096

    _instance = None

    @staticmethod
    def start_exiftool():
        """Instantiate ExifTool instance."""
        if shutil.which("exiftool") is None:
            logger.warning(
                f"{LOG_PREFIX} EXIF tags will not be copied because the `exiftool` "
                "executable could not be found. Please install exiftool and make sure "
                "it is on your $PATH."
            )
        else:
            ExifTool._instance = ExifTool()

    @staticmethod
    def copy_tags(src, dst):
        """Copy EXIF tags."""
        if ExifTool._instance is not None:
            ExifTool._instance._copy_tags(src, dst)

    @staticmethod
    def stop_exiftool():
        """Tear down ExifTool instance."""
        ExifTool._instance = None

    def __init__(self):
        """Invoke exiftool via subprocess call."""
        self.encoding = sys.getfilesystemencoding()
        if self.encoding != "mbcs":
            with contextlib.suppress(LookupError):
                codecs.lookup_error("surrogateescape")

        with open(os.devnull, "w") as devnull:
            self.process = subprocess.Popen(
                [
                    "exiftool",
                    "-stay_open",
                    "True",
                    "-@",
                    "-",
                    "-common_args",
                    "-G",
                    "-n",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=devnull,
            )

    def __del__(self):
        """Terminate process if still present."""
        if self.process is not None:
            self.process.terminate()

    def _copy_tags(self, src, dst):
        params = (
            b"-TagsFromFile",
            src.encode(self.encoding, ExifTool.errors),
            b'"-all:all>all:all"',
            dst.encode(self.encoding, ExifTool.errors),
        )
        self._send_command(params)
        params = (b"-delete_original!", dst.encode(self.encoding, ExifTool.errors))
        self._send_command(params)

    def _send_command(self, params):
        self.process.stdin.write(b"\n".join((*params, b"-j\n", b"-execute\n")))
        self.process.stdin.flush()
        output = b""
        fd = self.process.stdout.fileno()
        while not output.strip().endswith(ExifTool.sentinel):
            output += os.read(fd, ExifTool.block_size)
        exiftool_result = output.strip()[: -len(ExifTool.sentinel)]
        logger.debug(
            "{} exiftool result: {}".format(LOG_PREFIX, exiftool_result.decode("utf-8"))
        )


def convert_box(image, top, left, right, bottom):
    """Convert box coordinates strings to integer.

    t, l, r, b (top, left, right, bottom) must be strings specifying
    either a number or a percentage.
    """
    top = image.height * float(top[:-1]) / 100.0 if top[-1] == "%" else float(top)
    left = image.width * float(left[:-1]) / 100.0 if left[-1] == "%" else float(left)
    right = (
        image.width * float(right[:-1]) / 100.0 if right[-1] == "%" else float(right)
    )
    if bottom[-1] == "%":
        bottom = image.height * float(bottom[:-1]) / 100.0
    else:
        bottom = float(bottom)

    return top, left, right, bottom


def crop(i, left, top, right, bottom):
    """Crop image i to the box (left, top)-(right, bottom).

    left, top, right, bottom must be strings specifying
    either a number or a percentage.
    """
    top, left, right, bottom = convert_box(i, top, left, right, bottom)
    return i.crop((int(left), int(top), int(right), int(bottom)))


def resize(i, w, h):
    """Resize the image to the dimension specified.

    w, h (width, height) must be strings specifying either a number
    or a percentage.
    """
    _, _, w, h = convert_box(i, "0", "0", w, h)

    if i.mode == "P":
        i = i.convert("RGBA")
    elif i.mode == "1":
        i = i.convert("L")

    return i.resize((int(w), int(h)), Image.Resampling.LANCZOS)


def scale(i, w, h, upscale, inside):
    """Resize the image to the dimension specified, keeping the aspect ratio.

    w, h (width, height) must be strings specifying either a number
    or a percentage, or "None" to ignore this constraint.

    If upscale is True, upscaling is allowed.

    If inside is True, the resulting image will not be larger than the
    dimensions specified, else it will not be smaller.
    """
    iw = i.width
    ih = i.height

    if w == "None":
        w = 1.0
    elif w[-1] == "%":
        w = float(w[:-1]) / 100.0
    else:
        w = float(w) / iw

    if h == "None":
        h = 1.0
    elif h[-1] == "%":
        h = float(h[:-1]) / 100.0
    else:
        h = float(h) / ih

    scale = min(w, h) if inside else max(w, h)

    if upscale in [0, "0", "False", False]:
        scale = min(scale, 1.0)

    if i.mode == "P":
        i = i.convert("RGBA")
    elif i.mode == "1":
        i = i.convert("L")

    return i.resize((int(scale * iw), int(scale * ih)), Image.Resampling.LANCZOS)


def rotate(i, degrees):
    if i.mode == "P":
        i = i.convert("RGBA")
    elif i.mode == "1":
        i = i.convert("L")

    # rotate does not support the LANCZOS filter (Pillow 2.7.0).
    return i.rotate(int(degrees), Image.Resampling.BICUBIC, True)


def apply_filter(i, f):
    if i.mode == "P":
        i = i.convert("RGBA")
    elif i.mode == "1":
        i = i.convert("L")

    return i.filter(f)


basic_ops = {
    "crop": crop,
    "flip_horizontal": lambda i: i.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    "flip_vertical": lambda i: i.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
    "grayscale": lambda i: i.convert("L"),
    "resize": resize,
    "rotate": rotate,
    "scale_in": functools.partial(scale, inside=True),
    "scale_out": functools.partial(scale, inside=False),
    "blur": functools.partial(apply_filter, f=ImageFilter.BLUR),
    "contour": functools.partial(apply_filter, f=ImageFilter.CONTOUR),
    "detail": functools.partial(apply_filter, f=ImageFilter.DETAIL),
    "edge_enhance": functools.partial(apply_filter, f=ImageFilter.EDGE_ENHANCE),
    "edge_enhance_more": functools.partial(
        apply_filter, f=ImageFilter.EDGE_ENHANCE_MORE
    ),
    "emboss": functools.partial(apply_filter, f=ImageFilter.EMBOSS),
    "find_edges": functools.partial(apply_filter, f=ImageFilter.FIND_EDGES),
    "smooth": functools.partial(apply_filter, f=ImageFilter.SMOOTH),
    "smooth_more": functools.partial(apply_filter, f=ImageFilter.SMOOTH_MORE),
    "sharpen": functools.partial(apply_filter, f=ImageFilter.SHARPEN),
}


def set_default_settings(settings):
    # Set default value for 'IMAGE_PROCESS'.
    if "IMAGE_PROCESS" not in settings:
        logger.warning(f"{LOG_PREFIX} No processing instructions defined.")
        settings["IMAGE_PROCESS"] = {}

    # Set default value for 'IMAGE_PROCESS_DIR'.
    if "IMAGE_PROCESS_DIR" not in settings:
        settings["IMAGE_PROCESS_DIR"] = "derivatives"

    # Set default value for 'IMAGE_PROCESS_ENCODING'
    if "IMAGE_PROCESS_ENCODING" not in settings:
        settings["IMAGE_PROCESS_ENCODING"] = "utf-8"

    # Set default value for 'IMAGE_PROCESS_COPY_EXIF_TAGS'
    if "IMAGE_PROCESS_COPY_EXIF_TAGS" not in settings:
        settings["IMAGE_PROCESS_COPY_EXIF_TAGS"] = False

    # Set default value for 'IMAGE_PROCESS_FORCE'.
    if "IMAGE_PROCESS_FORCE" not in settings:
        settings["IMAGE_PROCESS_FORCE"] = False


def harvest_images(path, context):
    set_default_settings(context)

    logger.debug("%s harvesting %r", LOG_PREFIX, path)
    with open(path, "r+", encoding=context["IMAGE_PROCESS_ENCODING"]) as f:
        res = harvest_images_in_fragment(f, context)
        f.seek(0)
        f.truncate()
        f.write(res)


def harvest_feed_images(path, context, feed):
    set_default_settings(context)

    with open(path, "r+", encoding=context["IMAGE_PROCESS_ENCODING"]) as f:
        soup = BeautifulSoup(f, "xml", preserve_whitespace_tags={"rss", "feed"})

        for content in soup.find_all("content"):
            if content["type"] != "html" or not content.string:
                continue

            doc = html.unescape(content.string)
            res = harvest_images_in_fragment(doc, context)
            content.string = res
        f.seek(0)
        f.truncate()
        f.write(str(soup))


def harvest_images_in_fragment(fragment, settings):
    parser = settings.get("IMAGE_PROCESS_PARSER", "html.parser")
    soup = BeautifulSoup(fragment, parser, preserve_whitespace_tags={"html"})

    copy_exif_tags = settings.get("IMAGE_PROCESS_COPY_EXIF_TAGS", False)
    if copy_exif_tags:
        ExifTool.start_exiftool()

    for img in soup.find_all("img", class_=IMAGE_PROCESS_REGEX):
        for c in img["class"]:
            if c.startswith("image-process-"):
                derivative = c[14:]

                # Determine whether to modify the class attribute.
                add_class = settings.get("IMAGE_PROCESS_ADD_CLASS", True)
                if not add_class:
                    # Remove class if it's the only one, otherwise remove specific entry
                    img["class"].remove(c)
                    if len(img["class"]) == 0:
                        del img["class"]
                else:
                    class_prefix = settings.get(
                        "IMAGE_PROCESS_CLASS_PREFIX", "image-process-"
                    )
                    if class_prefix != "image-process-":
                        img["class"].remove(c)
                        img["class"].append(f"{class_prefix}{derivative}")
                break
        else:
            continue

        try:
            d = settings["IMAGE_PROCESS"][derivative]
        except KeyError as e:
            raise RuntimeError(f"Derivative {derivative} undefined.") from e

        if isinstance(d, list):
            # Single source image specification.
            process_img_tag(img, settings, derivative)

        elif not isinstance(d, dict):
            raise TypeError(
                f"Derivative {derivative} definition not handled (must be list or dict)"
            )

        elif "type" not in d:
            raise RuntimeError(f'"type" is mandatory for {derivative}.')

        elif d["type"] == "image":
            # Single source image specification.
            process_img_tag(img, settings, derivative)

        elif d["type"] == "responsive-image" and "srcset" not in img.attrs:
            # srcset image specification.
            build_srcset(img, settings, derivative)

        elif d["type"] == "picture":
            # Multiple source (picture) specification.
            group = img.find_parent()
            if group.name == "div":
                convert_div_to_picture_tag(soup, img, group, settings, derivative)
            elif group.name == "picture":
                process_picture(soup, img, group, settings, derivative)

    ExifTool.stop_exiftool()
    return str(soup)


def compute_paths(img, settings, derivative):
    process_dir = settings["IMAGE_PROCESS_DIR"]
    img_src = urlparse(img["src"])
    img_src_path = url2pathname(img_src.path.lstrip("/"))
    img_src_dirname, filename = os.path.split(img_src_path)
    derivative_path = os.path.join(process_dir, derivative)
    # urljoin truncates leading ../ elements
    base_url = posixpath.join(
        posixpath.dirname(img["src"]), pathname2url(str(derivative_path))
    )

    PELICAN_V4 = 4
    if pelican_version != "unknown" and int(pelican_version.split(".")[0]) < PELICAN_V4:
        file_paths = settings["filenames"]
    else:
        file_paths = settings["static_content"]

    for _f, contobj in file_paths.items():
        save_as = contobj.get_url_setting("save_as")
        # save_as can be set to empty string, which would match everything
        if save_as and img_src_path.endswith(save_as):
            source = contobj.source_path
            base_path = os.path.join(
                contobj.settings["OUTPUT_PATH"],
                os.path.dirname(contobj.get_url_setting("save_as")),
                process_dir,
                derivative,
            )
            break
    else:
        if "SITEURL" in settings:
            site_url = urlparse(settings["SITEURL"])
            site_url_path = url2pathname(site_url.path[1:])
        else:
            # if SITEURL is undefined, don't break!
            site_url_path = None

        if site_url_path:
            src_path = img_src_path.partition(site_url_path)[2].lstrip("/")
        else:
            src_path = img_src_path.lstrip("/")
        source = os.path.join(settings["PATH"], src_path)
        base_path = os.path.join(
            settings["OUTPUT_PATH"], os.path.dirname(src_path), str(derivative_path)
        )

    return Path(base_url, source, base_path, filename)


def process_img_tag(img, settings, derivative):
    path = compute_paths(img, settings, derivative)
    process = settings["IMAGE_PROCESS"][derivative]

    img["src"] = posixpath.join(path.base_url, path.filename)
    destination = os.path.join(str(path.base_path), path.filename)

    if not isinstance(process, list):
        process = process["ops"]

    process_image((path.source, destination, process), settings)


def format_srcset_element(path, condition):
    # space and comma have special meaning in srcset
    if " " in path or "," in path:
        path = urllib.parse.quote(path)

    return f"{path} {condition}"


def build_srcset(img, settings, derivative):
    path = compute_paths(img, settings, derivative)
    process = settings["IMAGE_PROCESS"][derivative]

    default = process["default"]
    default_name = ""
    if isinstance(default, str):
        breakpoints = {i for i, _ in process["srcset"]}
        if default not in breakpoints:
            logger.error(
                '%s srcset "%s" does not define default "%s"',
                LOG_PREFIX,
                derivative,
                default,
            )
        default_name = default
    elif isinstance(default, list):
        default_name = "default"
        destination = os.path.join(str(path.base_path), default_name, path.filename)
        process_image((path.source, destination, default), settings)

    img["src"] = posixpath.join(path.base_url, default_name, path.filename)

    if "sizes" in process:
        img["sizes"] = process["sizes"]

    srcset = []
    for src in process["srcset"]:
        file_path = posixpath.join(path.base_url, src[0], path.filename)
        srcset.append(format_srcset_element(file_path, src[0]))
        destination = os.path.join(str(path.base_path), src[0], path.filename)
        process_image((path.source, destination, src[1]), settings)

    if len(srcset) > 0:
        img["srcset"] = ", ".join(srcset)


def convert_div_to_picture_tag(soup, img, group, settings, derivative):
    """Convert a div containing multiple images to a picture."""
    process_dir = settings["IMAGE_PROCESS_DIR"]
    # Compile sources URL. Special source "default" uses the main
    # image URL. Other sources use the img with classes
    # [source['name'], 'image-process'].  We also remove the img from
    # the DOM.
    sources = copy.deepcopy(settings["IMAGE_PROCESS"][derivative]["sources"])
    for s in sources:
        if s["name"] == "default":
            s["url"] = img["src"]
        else:
            candidates = group.find_all("img", class_=s["name"])
            for candidate in candidates:
                if "image-process" in candidate["class"]:
                    s["url"] = candidate["src"]
                    candidate.decompose()
                    break

        url_path, s["filename"] = os.path.split(s["url"])
        s["base_url"] = os.path.join(url_path, process_dir, derivative)
        s["base_path"] = os.path.join(settings["OUTPUT_PATH"], s["base_url"][1:])

    # If default is not None, change default img source to the image
    # derivative referenced.
    default = settings["IMAGE_PROCESS"][derivative]["default"]
    if default is not None:
        default_source_name = default[0]

        default_source = None
        for s in sources:
            if s["name"] == default_source_name:
                default_source = s
                break

        if default_source is None:
            raise RuntimeError(
                'No source matching "%s", referenced in default setting.',
                (default_source_name,),
            )

        if isinstance(default[1], str):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = "default"

            source = os.path.join(settings["PATH"], default_source["url"][1:])
            destination = os.path.join(
                default_source["base_path"],
                default_source_name,
                default_item_name,
                default_source["filename"],
            )
            process_image((source, destination, default[1]), settings)
        else:
            raise RuntimeError(
                "Unexpected type for the second value of tuple "
                'IMAGE_PROCESS["%s"]["default"]; expected string or list.',
                (derivative,),
            )

        # Change img src to url of default processed image.
        img["src"] = os.path.join(
            default_source["base_url"],
            default_source_name,
            default_item_name,
            default_source["filename"],
        )

    # Create picture tag.
    picture_tag = soup.new_tag("picture")
    for s in sources:
        # Create new <source>
        source_attrs = {k: s[k] for k in s if k in ["media", "sizes"]}
        source_tag = soup.new_tag("source", **source_attrs)

        srcset = []
        for src in s["srcset"]:
            url = os.path.join(s["base_url"], s["name"], src[0], s["filename"])
            srcset.append(format_srcset_element(str(url), src[0]))

            source = os.path.join(settings["PATH"], s["url"][1:])
            destination = os.path.join(s["base_path"], s["name"], src[0], s["filename"])
            process_image((source, destination, src[1]), settings)

        if len(srcset) > 0:
            source_tag["srcset"] = ", ".join(srcset)

        picture_tag.append(source_tag)

    # Wrap img with <picture>
    img.wrap(picture_tag)


def process_picture(soup, img, group, settings, derivative):
    """Convert a simplified picture to a full HTML picture. See following example.

    <picture>
        <source class="source-1" src="image1.jpg"></source>
        <source class="source-2" src="image2.jpg"></source>
        <img class="image-process-picture" src="image3.jpg"></img>
    </picture>

    to

    <picture>
        <source srcset="...image1.jpg..." media="..." sizes="..."></source>
        <source srcset="...image2.jpg..."></source>
        <source srcset="...image3.jpg..." media="..." sizes="..."></source>
        <img src=".../image3.jpg"></img>
    </picture>

    """
    process_dir = settings["IMAGE_PROCESS_DIR"]
    process = settings["IMAGE_PROCESS"][derivative]
    # Compile sources URL. Special source "default" uses the main
    # image URL. Other sources use the <source> with classes
    # source['name'].  We also remove the <source>s from the DOM.
    sources = copy.deepcopy(process["sources"])
    for s in sources:
        if s["name"] == "default":
            s["url"] = img["src"]
            source_attrs = {k: s[k] for k in s if k in ["media", "sizes"]}
            s["element"] = soup.new_tag("source", **source_attrs)
        else:
            s["element"] = group.find("source", class_=s["name"]).extract()
            s["url"] = s["element"]["src"]
            del s["element"]["src"]
            del s["element"]["class"]

        url_path, s["filename"] = os.path.split(s["url"])
        s["base_url"] = posixpath.join(url_path, process_dir, derivative)
        s["base_path"] = os.path.join(settings["OUTPUT_PATH"], s["base_url"][1:])

    # If default is not None, change default img source to the image
    # derivative referenced.
    default = process["default"]
    if default is not None:
        default_source_name = default[0]

        default_source = None
        for s in sources:
            if s["name"] == default_source_name:
                default_source = s
                break

        if default_source is None:
            raise RuntimeError(
                'No source matching "%s", referenced in default setting.',
                (default_source_name,),
            )

        if isinstance(default[1], str):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = "default"
            source = os.path.join(settings["PATH"], default_source["url"][1:])
            destination = os.path.join(
                default_source["base_path"],
                default_source_name,
                default_item_name,
                default_source["filename"],
            )

            process_image((source, destination, default[1]), settings)

        else:
            raise RuntimeError(
                "Unexpected type for the second value of tuple "
                'IMAGE_PROCESS["%s"]["default"]; expected string or list.',
                (derivative,),
            )

        # Change img src to url of default processed image.
        img["src"] = posixpath.join(
            default_source["base_url"],
            default_source_name,
            default_item_name,
            default_source["filename"],
        )

    # Generate srcsets and put back <source>s in <picture>.
    for s in sources:
        srcset = []
        for src in s["srcset"]:
            url = posixpath.join(s["base_url"], s["name"], src[0], s["filename"])
            srcset.append(format_srcset_element(str(url), src[0]))

            source = os.path.join(settings["PATH"], s["url"][1:])
            destination = os.path.join(s["base_path"], s["name"], src[0], s["filename"])
            process_image((source, destination, src[1]), settings)

        if len(srcset) > 0:
            # Append source elements to the picture in the same order
            # as they are found in
            # settings['IMAGE_PROCESS'][derivative]['sources'].
            s["element"]["srcset"] = ", ".join(srcset)
            img.insert_before(s["element"])


def try_open_image(path):
    try:
        i = Image.open(path)
    except UnidentifiedImageError:
        logger.warning(
            f'{LOG_PREFIX} Source image "{path}" is not supported by Pillow.'
        )
        raise
    except FileNotFoundError:
        logger.warning(f'{LOG_PREFIX} Source image "{path}" not found.')
        raise

    return i


def process_image(image, settings):
    # remove URL encoding to get to physical filenames
    image = list(image)
    image[0] = unquote(image[0])
    image[1] = unquote(image[1])
    # image[2] is the transformation

    # If original image is older than existing derivative, skip
    # processing to save time, unless user explicitly forced
    # image generation.
    if (
        settings["IMAGE_PROCESS_FORCE"]
        or not os.path.exists(image[1])
        or os.path.getmtime(image[0]) > os.path.getmtime(image[1])
    ):
        logger.debug(f"{LOG_PREFIX} Processing {image[0]} -> {image[1]}")

        try:
            i = try_open_image(image[0])
        except (UnidentifiedImageError, FileNotFoundError):
            return

        for step in image[2]:
            if callable(step):
                i = step(i)
            else:
                elems = step.split(" ")
                i = basic_ops[elems[0]](i, *(elems[1:]))

        os.makedirs(os.path.dirname(image[1]), exist_ok=True)

        # `save_all=True`  will allow saving multi-page (aka animated) GIF's
        # however, turning it on seems to break PNG support, and doesn't seem
        # to work on GIF's either...
        i.save(image[1], progressive=True)

        ExifTool.copy_tags(image[0], image[1])
    else:
        logger.debug(f"{LOG_PREFIX} Skipping {image[0]} -> {image[1]}")


def dump_config(pelican):
    set_default_settings(pelican.settings)

    logger.debug(
        "{} config:\n{}".format(
            LOG_PREFIX, pprint.pformat(pelican.settings["IMAGE_PROCESS"])
        )
    )


def register():
    signals.content_written.connect(harvest_images)
    signals.feed_written.connect(harvest_feed_images)
    signals.finalized.connect(dump_config)
