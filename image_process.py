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


def scale(i, w, h, inside):
    """Resize the image to the dimension specified, keeping the aspect
    ratio.

    w, h (width, height) must be strings specifying either a number
    or a percentage, or "None" to ignore this constraint.

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
        content_modified = False
        soup = BeautifulSoup(instance._content)

        if 'IMAGE_PROCESS_DIR' in instance.settings:
            dest_dir = instance.settings['IMAGE_PROCESS_DIR']
        else:
            dest_dir = 'derivatives'

        for img in soup.find_all('img', class_ = re.compile("image-process-[-a-zA-Z0-9_]+")):
            for c in img['class']:
                match = re.search(r"image-process-([-a-zA-Z0-9_]+)", c)
                if match is not None:
                    source = os.path.join(instance.settings['OUTPUT_PATH'], img['src'][1:])
                    derivative = match.group(1)

                    path, name = os.path.split(img['src'])
                    img['src'] = os.path.join(path, dest_dir, derivative, name)

                    path, name = os.path.split(source)
                    destination = os.path.join(path, dest_dir, derivative, name)

                    images.append((source, destination, derivative))

                    content_modified = True
                    break # for c in img['class']

        if content_modified:
            instance._content = soup.decode()


def process_images(p):
    for image in images:
        path, _ = os.path.split(image[1])
        try:
            os.makedirs(path)
        except OSError as e:
            if e.errno == 17:
                # Already exists
                pass

        i = Image.open(image[0])

        process = p.settings['IMAGE_PROCESS'][image[2]]
        for step in process:
            if hasattr(step, '__call__'):
                i = step(i)
            else:
                elems = step.split(' ')
                i = basic_ops[elems[0]](i, *elems[1:])

        i.save(image[1])


def register():
    signals.content_object_init.connect(harvest_images)
    signals.finalized.connect(process_images)
