# -*- coding: utf-8 -*- #
"""
Image Process
=============

This plugin process images according to their class attribute.
"""
from __future__ import unicode_literals

import functools
import os.path
import re
import six

from PIL import Image, ImageFilter
from bs4 import BeautifulSoup
from pelican import signals

images = []

def convert_box(image, t, l, r, b):
    """Convert box coordinates strings to integer.

    t, l, r, b (top, left, right, bottom) must be strings specifying
    either a number or a percentage.
    """
    bbox = image.getbbox()
    iw = bbox[2] - bbox[0]
    ih = bbox[3] - bbox[1]

    if t[-1] == '%':
        t = ih * float(t[:-1]) / 100.
    else:
        t = float(t)
    if l[-1] == '%':
        l = iw * float(l[:-1]) / 100.
    else:
        l = float(l)
    if r[-1] == '%':
        r = iw * float(r[:-1]) / 100.
    else:
        r = float(r)
    if b[-1] == '%':
        b = ih * float(b[:-1]) / 100.
    else:
        b = float(b)

    return (t,l,r,b)


def crop(i, t, l, r, b):
    """Crop image i to the box (l,t)-(r,b).

    t, l, r, b (top, left, right, bottom) must be strings specifying
    either a number or a percentage.
    """
    t,l,r,b = convert_box(i, t, l, r, b)
    return i.crop((int(t),int(l),int(r),int(b)))


def resize(i, w, h):
    """Resize the image to the dimension specified.

    w, h (width, height) must be strings specifying either a number
    or a percentage.
    """
    _, _, w, h = convert_box(i, '0', '0', w, h)

    if i.mode == 'P':
        i = i.convert('RGBA')
    elif i.mode == '1':
        i = i.convert('L')

    return i.resize((int(w),int(h)), Image.LANCZOS)


def scale(i, w, h, upscale, inside):
    """Resize the image to the dimension specified, keeping the aspect
    ratio.

    w, h (width, height) must be strings specifying either a number
    or a percentage, or "None" to ignore this constraint.

    If upscale is True, upscaling is allowed.

    If inside is True, the resulting image will not be larger than the
    dimensions specified, else it will not be smaller.
    """
    bbox = i.getbbox()
    iw = bbox[2] - bbox[0]
    ih = bbox[3] - bbox[1]

    if w == 'None':
        w = 1.
    elif w[-1] == '%':
        w = float(w[:-1]) / 100.
    else:
        w = float(w) / iw

    if h == 'None':
        h = 1.
    elif h[-1] == '%':
        h = float(h[:-1]) / 100.
    else:
        h = float(h) / ih

    if inside:
        scale = min(w, h)
    else:
        scale = max(w, h)

    if upscale in [0, '0', 'False', False]:
        scale = min(scale, 1.)

    if i.mode == 'P':
        i = i.convert('RGBA')
    elif i.mode == '1':
        i = i.convert('L')

    return i.resize((int(scale*iw), int(scale*ih)), Image.LANCZOS)


def rotate(i, degrees):
    if i.mode == 'P':
        i = i.convert('RGBA')
    elif i.mode == '1':
        i = i.convert('L')

    # rotate does not support the LANCZOS filter (Pillow 2.7.0).
    return i.rotate(int(degrees), Image.BICUBIC, True)


def apply_filter(i, f):
    if i.mode == 'P':
        i = i.convert('RGBA')
    elif i.mode == '1':
        i = i.convert('L')

    return i.filter(f)


basic_ops = {
    'crop': crop,
    'flip_horizontal': lambda i: i.transpose(Image.FLIP_LEFT_RIGHT),
    'flip_vertical': lambda i: i.transpose(Image.FLIP_TOP_BOTTOM),
    'grayscale': lambda i: i.convert('L'),
    'resize': resize,
    'rotate': rotate,
    'scale_in': functools.partial(scale, inside=True),
    'scale_out': functools.partial(scale, inside=False),

    'blur': functools.partial(apply_filter, f=ImageFilter.BLUR),
    'contour': functools.partial(apply_filter, f=ImageFilter.CONTOUR),
    'detail': functools.partial(apply_filter, f=ImageFilter.DETAIL),
    'edge_enhance': functools.partial(apply_filter, f=ImageFilter.EDGE_ENHANCE),
    'edge_enhance_more': functools.partial(apply_filter, f=ImageFilter.EDGE_ENHANCE_MORE),
    'emboss': functools.partial(apply_filter, f=ImageFilter.EMBOSS),
    'find_edges': functools.partial(apply_filter, f=ImageFilter.FIND_EDGES),
    'smooth': functools.partial(apply_filter, f=ImageFilter.SMOOTH),
    'smooth_more': functools.partial(apply_filter, f=ImageFilter.SMOOTH_MORE),
    'sharpen': functools.partial(apply_filter, f=ImageFilter.SHARPEN),
    }


def harvest_images(instance):
    if instance._content is not None:
        instance._content = harvest_images_in_fragment(instance._content, instance.settings)

    for tag in iter(instance.metadata):
        fragment = getattr(instance, tag)
        if isinstance(fragment, six.string_types):
            fragment = harvest_images_in_fragment(fragment, instance.settings)
            setattr(instance, tag.lower(), fragment)
            instance.metadata[tag] = fragment


def harvest_images_in_fragment(fragment, settings):
    fragment_changed = False
    soup = BeautifulSoup(fragment)

    if 'IMAGE_PROCESS_DIR' in settings:
        dest_dir = settings['IMAGE_PROCESS_DIR']
    else:
        dest_dir = 'derivatives'

    for img in soup.find_all('img', class_ = re.compile("image-process-[-a-zA-Z0-9_]+")):
        for c in img['class']:
            match = re.search(r"image-process-([-a-zA-Z0-9_]+)", c)
            if match is not None:
                url_path, name = os.path.split(img['src'])

                source = os.path.join(settings['OUTPUT_PATH'], img['src'][1:])
                output_path, _ = os.path.split(source)

                derivative = match.group(1)

                if isinstance(settings['IMAGE_PROCESS'][derivative], list):
                    # Single source image specification.
                    img['src'] = os.path.join(url_path, dest_dir, derivative, name)
                    destination = os.path.join(output_path, dest_dir, derivative, name)
                    images.append((source, destination, settings['IMAGE_PROCESS'][derivative]))

                elif isinstance(settings['IMAGE_PROCESS'][derivative], dict):
                    # Multiple source image specification.
                    default_index = settings['IMAGE_PROCESS'][derivative]['default']
                    default_name = settings['IMAGE_PROCESS'][derivative]['srcset'][default_index][0]
                    img['src'] = os.path.join(url_path, dest_dir, derivative, default_name, name)

                    if 'sizes' in settings['IMAGE_PROCESS'][derivative]:
                        img['sizes'] = settings['IMAGE_PROCESS'][derivative]['sizes']

                    srcset = []
                    for src in settings['IMAGE_PROCESS'][derivative]['srcset']:
                        srcset.append("%s %s" % (os.path.join(url_path, dest_dir, derivative, src[0], name), src[0]))
                        destination = os.path.join(output_path, dest_dir, derivative, src[0], name)
                        images.append((source, destination, src[1]))

                    if len(srcset) > 0:
                        img['srcset'] = ', '.join(srcset)

                fragment_changed = True
                break # for c in img['class']

    if fragment_changed:
        # In Python 2, BeautifulSoup put our fragment inside html and
        # body tags, but in Python 3, it does not (maybe because it is
        # not using the same HTML parser).
        body = soup.find('body')
        if body:
            new_fragment = '';
            for element in body.children:
                new_fragment += element.decode()
        else:
            new_fragment = soup.decode()
    else:
        new_fragment = fragment

    return new_fragment


def process_images(p):
    for image in images:
        path, _ = os.path.split(image[1])
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno == 17:
                # Already exists
                pass

        # If original image is older than existing derivative, skip
        # processing to save time, unless user explicitely forced
        # image generation.
        if ('IMAGE_PROCESS_FORCE' in p.settings and p.settings['IMAGE_PROCESS_FORCE']) or \
                (not os.path.exists(image[1])) or \
                (os.path.getmtime(image[0]) > os.path.getmtime(image[1])):

            i = Image.open(image[0])

            for step in image[2]:
                if hasattr(step, '__call__'):
                    i = step(i)
                else:
                    elems = step.split(' ')
                    i = basic_ops[elems[0]](i, *elems[1:])

            i.save(image[1])

    # Clean up images global for the case where Pelican is running in
    # autoreload mode.
    del images[:]


def register():
    signals.content_object_init.connect(harvest_images)
    signals.finalized.connect(process_images)
