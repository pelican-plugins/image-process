# Image Process: A Plugin for Pelican

[![Build Status](https://img.shields.io/github/actions/workflow/status/pelican-plugins/image-process/main.yml?branch=main)](https://github.com/pelican-plugins/image-process/actions)
[![PyPI Version](https://img.shields.io/pypi/v/pelican-image-process)](https://pypi.org/project/pelican-image-process/)
[![Downloads](https://img.shields.io/pypi/dm/pelican-image-process)](https://pypi.org/project/pelican-image-process/)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)

*Image Process* is a plugin for [Pelican](https://getpelican.com),
a static site generator written in Python.

*Image Process* let you automate the processing of images based on their
class attribute. Use this plugin to minimize the overall page weight
and to save you a trip to Gimp or Photoshop each time you include an
image in your post.

*Image Process* also makes it easy to create responsive images using
the HTML5 `srcset` attribute and `<picture>` tag. It does this
by generating multiple derivative images from one or more sources.

*Image Process* will not overwrite your original images.

## Installation

The easiest way to install *Image Process* is via Pip. This
will also install the required dependencies automatically.

```sh
python -m pip install pelican-image-process
```

As long as you have not explicitly added a `PLUGINS` setting to your Pelican
settings file, then the newly-installed plugin should be automatically detected
and enabled. Otherwise, you must add `image_process` to your existing `PLUGINS`
list. For more information, please see the documentation regarding
[How to Use Plugins](https://docs.getpelican.com/en/latest/plugins.html#how-to-use-plugins).

You will then need to configure your desired transformations (see *Usage*
below) and add the appropriate class to images you want processed.

## Usage

*Image Process* scans your content for `<img>` tags with special
classes. It then maps the classes to a set of image processing
instructions, computes new images, and modifies HTML code according to
the instructions.

### Define Transformations

The first step in using this module is to define some image
transformations in your Pelican configuration file. Transformations
are defined in the `IMAGE_PROCESS` dictionary, mapping a
transformation name to a list of operations. There are three kinds of
transformations: image replacement, responsive image, and picture set.

#### Image Replacement

The simplest image processing will replace the original image by a
new, transformed image computed from the original. You may use this,
for example, to ensure that all images are of the same size, or to
compute a thumbnail from a larger image:

```python
IMAGE_PROCESS = {
    "article-image": ["scale_in 300 300 True"],
    "thumb": ["crop 0 0 50% 50%", "scale_out 150 150 True", "crop 0 0 150 150"],
}
```

These transformations tell *Image Process* to transform the image
referred to by the `src` attribute of an `<img>` according to the
list of operations specified, and replace the `src` attribute with the
URL of the transformed image.

For consistency with other types of transformations described
below, there is an alternative syntax for the processing instructions:

```python
IMAGE_PROCESS = {
    "thumb": {
        "type": "image",
        "ops": ["crop 0 0 50% 50%", "scale_out 150 150 True", "crop 0 0 150 150"],
    },
    "article-image": {
        "type": "image",
        "ops": ["scale_in 300 300 True"],
    },
}
```

To apply image replacement to the images in your articles, you must add to them
the special class `image-process-<transform>`, in which `<transform>` is the ID
of the transformation you wish to apply.

Let's say you have defined the transformation described above. To get your
image processed, it needs to have the right CSS class:

```html
<img class="image-process-article-image" src="/images/pelican.jpg" />
```

This can be produced in Markdown with:

```markdown
![](/images/pelican.png){: .image-process-article-image}
```

In reStructuredText, use the `:class:` attribute of the `image` or
the `figure` directive:

```rst
.. image:: /images/pelican.png
   :class: image-process-article-image
```

```rst
.. figure:: /images/pelican.png
    :class: image-process-article-image
```

⚠️ **Warning:**

> The reStructuredText reader will convert underscores (`_`) to
> dashes (`-`) in class names. To make sure everything runs
> smoothly, do not use underscores in your transformation names.

#### Responsive Images

You can use *Image Process* to automatically generate a set of
images that will be selected for display by browsers according to the
viewport width or according to the device resolution. To accomplish
this, *Image Process* will add a [`srcset` attribute](https://caniuse.com/srcset)
(and maybe a `media` and a `sizes` attribute) to the `<img>` tag.

HTML5 supports two types of responsive image sets. The first one is
device-pixel-ratio-based, selecting higher resolution images for higher
resolution devices; the second one is viewport-based, selecting
images according to the viewport size. You can read more about
[HTML5 responsive images][] for a gentle introduction to the `srcset`
and `<picture>` syntaxes.

To tell *Image Process* to generate a responsive image, add a
`responsive-image` transformation to your your `IMAGE_PROCESS`
dictionary, with the following syntax:

```python
IMAGE_PROCESS = {
    "crisp": {
        "type": "responsive-image",
        "srcset": [
            ("1x", ["scale_in 800 600 True"]),
            ("2x", ["scale_in 1600 1200 True"]),
            ("4x", ["scale_in 3200 2400 True"]),
        ],
        "default": "1x",
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
}
```

The `crisp` transformation is an example of a transformation
enabling device-pixel-ratio-based selection. The `srcset` is a list
of tuples, each tuple containing the image description (`"1x"`,
`"2x"`, etc.) and the list of operations to generate the derivative
image from the original image (the original image is the value of the
`src` attribute of the `<img>`). Image descriptions are hints
about the resolution of the associated image and must have the suffix
`x`. The `default` setting specifies the image to use to replace the `src`
attribute of the image. This is the image that will be displayed by
browsers that do not support the `srcset` syntax.

The `large-photo` transformation is an example of a transformation
enabling viewport-based selection. The `sizes` contains a rule to
compute the width of the displayed image from the width of the
viewport. Once the browser knows the image width, it will select an
image source from the `srcset`. The `srcset` is a list of tuple,
each tuple containing the image description (`"600w"`, `"800w"`,
etc.) and the list of operations to generate the derivative image from
the original image (the original image is the value of the `src`
attribute of the `<img>`). Image descriptions are hints about the
width in pixels of the associated image and must have the suffix
`w`. The `default` setting specifies the image to use to replace the `src`
attribute of the image. This is the image that will be displayed by
browsers that do not support the `srcset` syntax.

In the two examples above, the `default` setting is a string referring to
one of the images in the `srcset`. However, the `default` value
could also be a list of operations to generate a different derivative
image.

To make the images in your article responsive, you must add to them the
special class `image-process-<transform>`, in which `<transform>` is the ID of the
transformation you wish to apply, exactly like you would do for the
image replacement case, described above.

So, in HTML it should look like this:

```html
<img class="image-process-large-photo" src="/images/pelican.jpg" />
```

Which can be produced in Markdown with:

```markdown
![](/images/pelican.jpg){: .image-process-large-photo}
```

In reStructuredText, use the `:class:` attribute of the `image` or
the `figure` directive:

```rst
.. image:: /images/pelican.jpg
   :class: image-process-large-photo
```

```rst
.. figure:: /images/pelican.jpg
    :class: image-process-large-photo
```

#### Picture Set

*Image Process* can be used to generate the images used by a
`<picture>` tag. The `<picture>` syntax allows for more
flexibility in providing a choice of image to the browser.
Again, you can read more about [HTML5 responsive images][] for a
gentle introduction to the `srcset` and `<picture>` syntaxes.

To tell *Image Process* to generate the images for a `<picture>`,
add a `picture` entry to your `IMAGE_PROCESS` dictionary with the
following syntax:

```python
IMAGE_PROCESS = {
    "example-pict": {
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
                ]
            },
        ],
        "default": ("default", "640w"),
    },
}
```

Each of the `sources` entries is very similar to the `responsive
image` describe above. Here, each source must have a `name`, which
will be used to find the URL of the original image for this source in
your article. The source may also have a `media`, which contains a
rule used by the browser to select the active source. The `default`
setting specifies the image to use to replace the `src` attribute of
the `<img>` inside the `<picture>`. This is the image that will be
displayed by browsers that do not support the `<picture>` syntax. In
this example, it will use the image `640w` from the source `default`.
A list of operations could have been specified instead of `640w`.

To generate a responsive `<picture>` for the images in your
articles, you must add to your article a pseudo `<picture>` tag that
looks like this:

```html
<picture>
    <source class="source-1" src="/images/pelican-closeup.jpg"></source>
    <img class="image-process-example-pict" src="/images/pelican.jpg"/>
</picture>
```

Each `<source>` tag maps a source name (the `class` attribute) to
a file (the `src` attribute). The `<img>` must have the special
class `image-process-` followed by the name of the transformation
you wish to apply. The file referenced by the `src` attribute of the
`<img>` will be used as the special `default` source in your
transformation definition.

You can't produce this with pure Markdown and must instead resort to raw HTML.

In reStructuredText, however, you can also use the `figure` directive
to generate a `<picture>`. The figure image file will be used as the
special `default` source; other sources must be added in the legend
section of the `figure` as `image` directives. The figure class must
be `image-process-` followed by the name of the transformation you
wish to apply, while the other images must have two classes:
`image-process` and the name of the source they provide an image for:

```rst
.. figure:: /images/pelican.jpg
   :class: image-process-example-pict

    Test picture

    .. image:: /images/pelican-closeup.jpg
       :class: image-process source-1
```

The images in the legend section that are used as source for the
`<picture>` will be removed from the image legend, so that they do
not appear in your final article.

### Transformations

Available operations for transformations are:

* `crop <left> <top> <right> <bottom>`:

    Crop the image to the box (`<left>`, `<top>`)-(`<right>`, `<bottom>`). Values
    can be absolute (a number) or relative to the size of the image (a
    number followed by a percent sign `%`).

* `flip_horizontal`:

    Flip the image horizontally.

* `flip_vertical`:

    Flip the image vertically.

* `grayscale`:

    Convert the image to grayscale.

* `resize <width> <height>`:

    Resize the image. This operation does *not* preserve the image aspect
    ratio. Values can be absolute (a number) or relative to the
    size of the image (a number followed by a percent sign `%`).

* `rotate <degrees>`:

    Rotate the image.

* `scale_in <width> <height> <upscale>`:

    Resize the image. This operation preserves the image aspect ratio
    and the resulting image will be no larger than `<width>` x
    `<height>`. Values can be absolute (a number) or relative to the
    size of the image (a number followed by a percent sign `%`).
    If `<upscale>` is `False`, smaller images will not be enlarged.

* `scale_out <width> <height> <upscale>`:

    Resize the image. This operation preserves the image aspect ratio
    and the resulting image will be no smaller than `<width>` x
    `<height>`. Values can be absolute (a number) or relative to the
    size of the image (a number followed by a percent sign `%`).
    If `<upscale>` is `False`, smaller images will not be enlarged.

* `blur`:

    Apply the `pillow.ImageFilter.BLUR` filter to the image.

* `contour`:

    Apply the `pillow.ImageFilter.CONTOUR` filter to the image.

* `detail`:

    Apply the `pillow.ImageFilter.DETAIL` filter to the image.

* `edge_enhance`:

    Apply the `pillow.ImageFilter.EDGE_ENHANCE` filter to the image.

* `edge_enhance_more`:

    Apply the `pillow.ImageFilter.EDGE_ENHANCE_MORE` filter to the image.

* `emboss`:

    Apply the `pillow.ImageFilter.EMBOSS` filter to the image.

* `find_edges`:

    Apply the `pillow.ImageFilter.FIND_EDGES` filter to the image.

* `smooth`:

    Apply the `pillow.ImageFilter.SMOOTH filter` to the image.

* `smooth_more`:

    Apply the `pillow.ImageFilter.SMOOTH_MORE` filter to the image.

* `sharpen`:

    Apply the `pillow.ImageFilter.SHARPEN` filter to the image.

You can also define your own operations; the only requirement is that
your operation should be a callable object expecting a `pillow.Image` as
its first parameter and it should return the transformed image:

```python
def crop_face(image):
    """Detect face in image and crop around it."""
    # Fancy algorithm.
    return image

IMAGE_PROCESS = {
    "face-thumbnail": [crop_face, "scale_out 150 150 True"]
}
```

### Additional Settings

#### Destination Directory

By default, the new images will be stored in a directory named
`derivative/<TRANSFORMATION_NAME>` in the output folder at
the same location as the original image.
For example, if the original image is located in
the `content/images` folder, the computed images will be stored
in `output/images/derivative/<TRANSFORMATION_NAME>`.
All the transformations are done in the output directory in order
to avoid confusion with the source files or if we test multiple
transformations. You can replace `derivative` by something else using
the `IMAGE_PROCESS_DIR` setting in your Pelican settings file:

```python
IMAGE_PROCESS_DIR = "derivees"
```

#### Force Image Processing

If the transformed image already exists and is newer than the original
image, the plugin assumes that it should not re-compute it again. You
can force the plugin to re-compute all images by setting
`IMAGE_PROCESS_FORCE` to `True` in your Pelican configuration file.

```python
IMAGE_PROCESS_FORCE = True
```

#### Selecting a HTML Parser

You may select the HTML parser which is used. The default is the built-in
`html.parser` but you may also select `html5lib` or `lxml` by setting
`IMAGE_PROCESS_PARSER` in your Pelican settings file. For example:

```python
IMAGE_PROCESS_PARSER = "html5lib"
```

For details, refer to the [BeautifulSoup documentation on parsers][].

#### File Encoding

You may select a different file encoding to be used by BeautifulSoup as it
opens your files. The default is `utf-8`.

```python
IMAGE_PROCESS_ENCODING = "utf-8"
```

#### Copying EXIF Tags

You may ask *Image Process* to copy the EXIF tags from your original image to
the transformed images. You must have [exiftool](https://exiftool.org/) installed.

```python
IMAGE_PROCESS_COPY_EXIF_TAGS = True
```

Note that `exiftool` prior to version 12.46 cannot write WebP images, so if you work
with WebP images, you should use version 12.46 or later.

#### Modifying the `class` Attribute of Processed Images

By default, *Image Process* adds the `image-process-<transform>`
CSS class to transformed images. This behavior is controlled by the
`IMAGE_PROCESS_ADD_CLASS` setting (default: `True`) and the
`IMAGE_PROCESS_CLASS_PREFIX` setting (default: `"image-process-"`).

* If `IMAGE_PROCESS_ADD_CLASS` is `True`, the `<transform>` name is added
  to the `class` attribute of the image.
  You can customize the class prefix using `IMAGE_PROCESS_CLASS_PREFIX`.

* If `IMAGE_PROCESS_ADD_CLASS` is `False`, no class attribute will be added.

This setting allows you to control whether transformation details appear
in the HTML output or to avoid conflicts with custom styles.

```python
# Use a custom class prefix instead of "image-process-"
IMAGE_PROCESS_CLASS_PREFIX = "custom-prefix-"

# Disable adding transformation class attributes
IMAGE_PROCESS_ADD_CLASS = False
```

## Known Issues

* Pillow, when resizing animated GIF files, [does not return an animated file](https://github.com/pelican-plugins/image-process/issues/11).

## Contributing

Contributions are welcome and much appreciated. Every little bit helps. You can contribute by improving the documentation, adding missing features, and fixing bugs. You can also help out by reviewing and commenting on [existing issues][].

To start contributing to this plugin, review the [Contributing to Pelican][] documentation, beginning with the **Contributing Code** section.

[existing issues]: https://github.com/pelican-plugins/image-process/issues
[Contributing to Pelican]: https://docs.getpelican.com/en/latest/contribute.html

### Documenting Changes for Releases

When you include a `RELEASE.md` file in your pull request, we use
[AutoPub](https://justinmayer.com/projects/autopub/) to automatically update
the changelog and issue a new plugin release when your pull request is merged.
This `RELEASE.md` file is automatically deleted during the release process, so
it should not persistently exist in the repository, and thus you should create
it in the project root. This is a standard Markdown file, so you can add
Markdown as needed to concisely describe your changes.

When a release is issued, the description in the `RELEASE.md` file will be added to
the changelog and used to create release notes for the GitHub release.

You must specify a `Release type` line at the top of your `RELEASE.md`, which
is used to determine how to increment the release version number. It is
therefore important that you do not manually increment the version number in
the `pyproject.toml` file, as that will be handled automatically.

The format of a `RELEASE.md` file is therefore:

```md
Release type: patch

[details of changes]
```

Valid release types are: `patch`, `minor`, or `major`. Generally, we try and
follow [Semantic Versioning](https://semver.org/), which means:

- a **patch** (or bug-fix) release is one that fixes a bug in the project, but
  does not add features or require users to make any configuration changes.
- a **minor** (or feature) release is one that adds new features or
  configuration options to the project. It may also include bug fixes.
- a **major** (or “breaking”) release is one that changes how the end user
  interacts with the plugin, in a non-backwards-compatible way.

Generally speaking, the idea is to “ship early and often”. We therefore do not
hesitate to issue releases, even if they are small, so that we can ship new
features and fixes to users in a timely fashion.

### Regenerating Test Images

If you need to regenerate the transformed images used by the test suite, there
is a helper function to do this for you. From the Python REPL:

```python
>>> from pelican.plugins.image_process.test_image_process import generate_test_images
>>> generate_test_images()
36 test images generated!
```

## License

This project is licensed under the [AGPL-3.0 license](http://www.gnu.org/licenses/agpl-3.0.html).

The [pelican image](https://web.archive.org/web/20090505115626/http://www.pdphoto.org/PictureDetail.php?mat=&pg=5726) in the test data is by Jon Sullivan, published under a [Creative Commons Public Domain license](https://creativecommons.org/licenses/publicdomain/).

[HTML5 responsive images]: https://www.smashingmagazine.com/2014/05/14/responsive-images-done-right-guide-picture-srcset/
[BeautifulSoup documentation on parsers]: https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser
