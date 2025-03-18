CHANGELOG
=========

3.1.0 - 2025-03-18
------------------

* *Feature:* Add `IMAGE_PROCESS_ADD_CLASS` and `IMAGE_PROCESS_CLASS_PREFIX` settings to control
the `image-process-<transform>` CSS class assignment for processed images.
* *Fix*: Encode URLs in `srcset` when they contain a space or a comma, as those characters have a special meaning in the context of a `srcset` value.
* *Fix:* Improve operations for images with empty margins by using `image.width`/`image.height` instead of `bbox`.
* *Fix:* Preserve HTML indentation when rewriting content.
* *Fix:* Avoid loading images needlessly by only processing images if Pillow can handle them.
* *Tests:* Make tests more resilient to small pixel content differences on ARM vs. Intel architectures.
* *Docs:* Correct cropping transformation values.

Contributed by [Justin Mayer](https://github.com/justinmayer) via [PR #94](https://github.com/pelican-plugins/image-process/pull/94/)


3.0.4 - 2024-03-08
------------------

Remove upper bounds on several dependency versions.

Contributed by [Justin Mayer](https://github.com/justinmayer) via [PR #81](https://github.com/pelican-plugins/image-process/pull/81/)


3.0.3 - 2022-07-18
------------------

*support*: Display plugin configuration when Pelican is run in debug mode.

3.0.2 - 2022-07-11
------------------

*support*: Add Pillow 10 to list of supported versions.

3.0.1 - 2022-07-11
------------------

*bug*: Fix function calls to be deprecated by Pillow 10.

3.0.0 - 2022-07-10
------------------

*support*: Drops support for Python 3.6.

*support*: upgrade Pillow to 9.0.0 (which doesn't support Python 3.6)

*support*: regenerate test images to match new output from Pillow 9

2.1.3 - 2021-07-09
------------------

*bug*: handling edge cases where image is location is non-local to the Pelican site source,
does not exist, or cannot be identified by Pillow.

Contributed by [Lucas Cimon](https://github.com/Lucas-C) [PR #51](https://github.com/pelican-plugins/image-process/pull/51/)


2.1.2 - 2021-05-28
------------------

*bug*: Add [lxml](https://lxml.de/) as a project requirement. It is used to
parse Atom and RSS feeds.

2.1.1 - 2021-05-07
------------------

- **Support**: Support Pelican from v3.0 on. See [Pull Request
  #47](https://github.com/pelican-plugins/image-process/pull/47)
- **Support**: Re-enable Windows support for development tools, specifically
  the project's `tasks.py` file for use with *Invoke*.

2.1.0 - 2021-03-11
------------------

- **feature**: Add setting to copy EXIF tags from source images to processed
  images. See [Pull Request
  #41](https://github.com/pelican-plugins/image-process/pull/41) by
  [@patrickfournier](https://github.com/patrickfournier).

2.0.0 - 2020-12-04
------------------

- **feature**: Support `srcset` generation inside Atom feeds. See [Pull Request
  #29](https://github.com/pelican-plugins/image-process/pull/29) by
  [@MicroJoe](https://github.com/MicroJoe).
- **feature**: Generate progressive JPEGs. See [Pull Request
  #17](https://github.com/pelican-plugins/image-process/pull/17) by
  [@Lucas-C](https://github.com/Lucas-C).
- **bug** (Breaking Change): fix `crop` API. See [Pull Request
  #14](https://github.com/pelican-plugins/image-process/pull/14).
- **support**: Convert to namespace plugin. The import path of the plugin is
  now `pelican.plugins.image_process`. See [Pull Request
  #38](https://github.com/pelican-plugins/image-process/pull/38).
- **support**: Transfer stewardship of the project to the
  [Pelican-Plugins](https://github.com/pelican-plugins) organization. The
  projects code repo is now at
  <https://github.com/pelican-plugins/image-process>. See [Issue
  #32](https://github.com/pelican-plugins/image-process/issues/32).

1.3.0 - 2019-10-26
------------------

A new release to PyPI intended to replace the Git submodule-based installation,
while providing the following improvements along with MinchinWeb’s earlier
ones. The plugin is available at
[pelican-image-process](https://pypi.org/project/pelican-image-process/). See
[Issue #13](https://github.com/pelican-plugins/image-process/issues/13).

The project returns to the stewardship of
[WhiskyEchoBravo](https://github.com/whiskyechobravo/image_process).

[@MinchinWeb](https://github.com/MinchinWeb) did a good job on this project
while it was not maintained. Thanks!

**The following changelog is from `minchin.pelican.plugins.image_process`:**

1.2.1 - 2021-04-26
------------------

- **support**: Add deprecation notice to point to new plugin location at
  `pelican-image-process` on PyPI.

1.2.0 - 2019-08-17
------------------

- **feature**: Add support for Pelican v4. See [Issue
  #5](https://github.com/MinchinWeb/minchin.pelican.plugins.image_process/issues/5).
- **bug**: Remove dependency on ``pelican.tests``. See [Issue
  #1](https://github.com/MinchinWeb/minchin.pelican.plugins.image_process/issues/1).

1.1.4 - 2018-01-03
------------------

- **bug**: Fixing a bug when we use `{attach}` on an article (thanks
  [@cunhaax](https://github.com/cunhaax)). See [Pull Request
  #4](https://github.com/MinchinWeb/minchin.pelican.plugins.image_process/pull/4).
- **bug**: fix order of arguments for crop command. See [Issue
  #3](https://github.com/MinchinWeb/minchin.pelican.plugins.image_process/issues/3).
- **bug**: `pep8` is now `pycodestyle`

1.1.3 - 2017-05-27
------------------

- **bug**: make code on PyPI match code on Git. See [Issue #2](https://github.com/MinchinWeb/minchin.pelican.plugins.image_process/issues/2).

1.1.2 - 2017-04-10
------------------

- **bug**:  upgrade release toolchain
- **bug**:  `Framework :: Pelican :: Plugins` trove classifier for PyPI now
  available

1.1.1 - 2017-03-08
------------------

- **bug**:  provide universal wheels

1.1.0 - 2016-09-12
------------------

- **feature**: allow definition of file encoding (using
  ``IMAGE_PROCESS_ENCODING`` variable) in Pelican configuration
- **bug**: deal with undefined ``SITEURL``
- **support**: first release to PyPI under
  [minchin.pelican.plugins.image-process](https://pypi.org/project/minchin.pelican.plugins.image-process/#history).
- **support**: add release machinery

1.0.2 - 2016-08-12
------------------

- **bug**: fix problems dealing with escaped URL's
- **support**: move package to *minchin.pelican.plugins.image_process*
- **support**: add `setup.py`

1.0.1 - 2016-06-19
------------------

- **bug**: merge in open [Pull Request
  #8](https://github.com/whiskyechobravo/image_process/pull/8) by [Peter
  Dahlberg](https://github.com/catdog2) which fixes issues computing image file
  paths

1.0.0 - 2016-06-12
------------------

- **support**: copy existing code from
  [WhiskyEchoBravo](https://github.com/whiskyechobravo/image_process).
