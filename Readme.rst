==============
 Image Process
==============

This plugin let you automate the processing of images based on their
class attribute. Use this plugin to minimize the overall page weight
and to save you a trip to Gimp or Photoshop each time you include an
image in your post. The plugin supports the ``srcset`` attribute by
generating multiple images from one source, if requested.

This plugin will not overwrite your original images.

This plugin does not (yet) generate ``<picture>`` tags.

Requirements
============

This plugin requires Beautiful Soup and Pillow. Both can be installed
with pip:

.. code-block:: sh

   pip install pillow beautifulsoup4

If you encounter errors while processing JPEG files, you may need to install
the JPEG development library:

.. code-block:: sh

   pip uninstall pillow
   apt-get install libjpeg-dev
   pip install pillow


Usage
=====

This plugin works by scanning your content for ``<img>`` tags with
special classes, computing new images according to the class name it
found, replacing the ``src`` attribute and adding a ``srcset``
attribute if necessary.


Define transformations
----------------------

The first step is to define some image transformations in your Pelican
configuration file. Transformations are defined in the
``IMAGE_PROCESS`` dictionary, mapping a transformation name to a
list of operations:

.. code-block:: python

  IMAGE_PROCESS = {
      'thumb': ["crop 0 0 50% 50%", "scale_out 150 150", "crop 0 0 150 150"],
      'article-image': ["scale_in 300 300"],
      'crisp': { 'srcset': [('1x', ["scale_in 800 600 True"]),
                            ('2x', ["scale_in 1600 1200 True"]),
                            ('4x', ["scale_in 3200 2400 True"]),
                           ],
                 'default': '1x',
               },
      'large-photo': { 'sizes': '(min-width: 1200px) 800px, (min-width: 992px) 650px, \
                                 (min-width: 768px) 718px, 100vw',
                       'srcset': [('600w', ["scale_in 600 450 True"]),
                                  ('800w', ["scale_in 800 600 True"]),
                                  ('1600w', ["scale_in 1600 1200 True"]),
                                  ],
                       'default': '800w',
                     },
      }

.. note::

   If you are writing content in reStructuredText, do not use
   underscores (``_``) in your transformation names.

The ``thumb`` and the ``article-image`` transformations define simple
transformations: the original image will be transformed by applying
the list of operations specified and the ``src`` attribute of the
``<img>`` will be replaced by the URL of the transformed image.

The ``crisp`` and the ``large-photo`` transformations take advantage
of the ``srcset`` attribute to define responsive images (see `this
article`_ for a gentle introduction to ``srcset`` and
``<picture>``). The ``crisp`` transformation is an example of a
transformation enabling device-pixel-ratio-based selection, while the
``large-photo`` transformation is an example of viewport-based
selection. Each of the transformation in the ``srcset`` list will be
used to generate a new image that will be attached, along with its
description, to the ``srcset`` attribute of the ``<img>`` element,
while its ``src`` attribute will be replaced by the ``default`` image
URL. If present, the ``sizes`` string will become the ``sizes``
attribute of the ``<img>``.

The ``default`` value can either be:

- a string specifying the name of the transformation in the ``srcset``
  array to use as default;
- a list of operation to compute the default image.

.. _this article: http://www.smashingmagazine.com/2014/05/14/responsive-images-done-right-guide-picture-srcset/

Available operations for transformations are:

crop *top* *left* *right* *bottom*
  Crop the image to the box (*left*, *top*)-(*right*, *bottom*). Values
  can be absolute (a number) or relative to the size of the image (a
  number followed by a percent sign ``%``).

flip_horizontal
  Flip the image horizontally.

flip_vertical
  Flip the image vertically.

grayscale
  Convert the image to grayscale.

resize *width* *height*
  Resize the image. This operation does *not* preserve the image aspect
  ratio. Values can be absolute (a number) or relative to the
  size of the image (a number followed by a percent sign ``%``).

rotate degree
  Rotate the image.

scale_in *width* *height*
  Resize the image. This operation preserves the image aspect ratio
  and the resulting image will be no larger than *width* x
  *height*. Values can be absolute (a number) or relative to the
  size of the image (a number followed by a percent sign ``%``).

scale_out
  Resize the image. This operation preserves the image aspect ratio
  and the resulting image will be no smaller than *width* x
  *height*. Values can be absolute (a number) or relative to the
  size of the image (a number followed by a percent sign ``%``).

blur
  Apply the ``pillow.ImageFilter.BLUR`` filter to the image.

contour
  Apply the ``pillow.ImageFilter.CONTOUR`` filter to the image.

detail
  Apply the ``pillow.ImageFilter.DETAIL`` filter to the image.

edge_enhance
  Apply the ``pillow.ImageFilter.EDGE_ENHANCE`` filter to the image.

edge_enhance_more
  Apply the ``pillow.ImageFilter.EDGE_ENHANCE_MORE`` filter to the image.

emboss
  Apply the ``pillow.ImageFilter.EMBOSS`` filter to the image.

find_edges
  Apply the ``pillow.ImageFilter.FIND_EDGES`` filter to the image.

smooth
  Apply the ``pillow.ImageFilter.SMOOTH filter`` to the image.

smooth_more
  Apply the ``pillow.ImageFilter.SMOOTH_MORE`` filter to the image.

sharpen
  Apply the ``pillow.ImageFilter.SHARPEN`` filter to the image.


You can also define your own operations; the only requirement is that
your operation should be a callable object expecting a ``pillow.Image`` as
its first parameter and it should return the transformed image:

.. code-block:: python

  def crop_face(image):
      """Detect face in image and crop around it."""
      # TODO: Fancy algorithm.
      return image

  IMAGE_PROCESS = {
      'face-thumbnail': [crop_face, "scale_out 150 150"]
      }


Applying the transformations
----------------------------

To apply the transformations to your images, you must add them the
special class ``image-process-`` followed by the name of the
transformation you wish to apply. For example, let's pretend you have
defined the ``face-thumbnail`` transformation described above. If you
write your content in HTML or in Markdown, do something like this:

.. code-block:: html

  <img class="image-process-face-thumbnail" src="/images/me.jpg"/>


In reStructuredText, you can use the ``:class:`` attribute of the
``image`` of the ``figure`` directive:

.. code-block:: rst

   .. image:: /images/me.png
      :class: image-process-face-thumbnail

.. note::

   The reStructuredText reader will convert underscores (``_``) to
   dashes (``-``) in class names. To make sure everything runs
   smoothly, do not use underscores in your transformation names.


Additional settings
-------------------

Destination directory
~~~~~~~~~~~~~~~~~~~~~

By default, the new images will be stored in a directory named
``derivative/<TRANSFORMATION_NAME>`` in the directory of the original
image. You can replace ``derivative`` by something else using the
``IMAGE_PROCESS_DIR`` setting in your Pelican configuration file:

.. code-block:: python

   IMAGE_PROCESS_DIR = 'derivees'


Force image processing
~~~~~~~~~~~~~~~~~~~~~~

If the transformed image already exists and is newer than the original
image, the plugin assumes that it should not recompute it again. You
can force the plugin to recompute all images by setting
``IMAGE_PROCESS_FORCE`` to True in your Pelican configuration file.

.. code-block:: python

   IMAGE_PROCESS_FORCE = True


Credits
-------

Pelican image in test data by Jon Sullivan. Source:
http://www.pdphoto.org/PictureDetail.php?mat=&pg=5726
