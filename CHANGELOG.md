CHANGELOG
=========

2.1.0 - 2021-03-11
------------------

Add setting to copy EXIF tags from source images to processed images

2.0.0 - 2020-12-04
------------------

* Convert to namespace plugin
* Support `srcset` generation inside Atom feeds
* Generate progressive JPEGs

1.3.0 - 2019-10-26
------------------

A new release to PyPI intended to replace the Git submodule-based installation,
while providing the following improvements along with Minchin’s earlier ones:

**The following changelog is from `minchin.pelican.plugins.image_process`:**

[@Minchin](https://github.com/MinchinWeb) did a good job on this project while it was not maintained. Thanks!

- :release:`1.2.0 <2019-08-17>`
- :bug:`1 major` remove dependency on ``pelican.tests``
- :feature:`5` add support for Pelican v4
- :release:`1.1.4 <2018-01-03>`
- :bug:`4` Fixing a bug when we use ``{attach}`` on an article (thanks
  `@cunhaax <https://github.com/cunhaax>`_)
- :bug:`3` fix order of arguments for crop command
- :bug:`-` ``pep8`` is now ``pycodestyle``
- :release:`1.1.3 <2017-05-27>`
- :bug:`2` make code on PyPI match code on Git
- :release:`1.1.2 <2017-04-10>`
- :bug:`-` upgrade release toolchain
- :bug:`-` ``Framework :: Pelican :: Plugins`` trove classifier for PyPI now
  available
- :release:`1.1.1 <2017-03-08>`
- :bug:`-` provide universal wheels
- :release:`1.1.0 <2016-09-12>`
- :support:`-` first release to PyPI
- :support:`-` add release machinery
- :bug:`- major` deal with undefined ``SITEURL``
- :feature:`-` allow defination of file encoding (using
  ``IMAGE_PROCESS_ENCODING`` variable) in Pelican configuration
- :release:`1.0.2 <2016-08-12>`
- :support:`-` move package to 'minchin.pelican.plugins.image_process'
- :support:`-` add 'setup.py'
- :bug:`-` fix problems dealing with escaped URL's
- :release:`1.0.1 <2016-06-19>`
- :bug:`-` merge in open `Pull Request #8
  <https://github.com/whiskyechobravo/image_process/pull/8>`_ by
  `Peter Dahlberg <https://github.com/catdog2>`_ by which fixes issues
  computing image file paths
- :release:`1.0.0 <2016-06-12>`
- :support:`-` copy exising code from
  https://github.com/whiskyechobravo/image_process
