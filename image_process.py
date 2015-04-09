# -*- coding: utf-8 -*- #
"""
Image Process
=============

This plugin process images according to their class attribute.
"""
from __future__ import unicode_literals

import copy
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
    # Set default value for 'IMAGE_PROCESS_DIR'.
    if 'IMAGE_PROCESS_DIR' not in instance.settings:
        instance.settings['IMAGE_PROCESS_DIR'] = 'derivatives'

    if instance._content is not None:
        instance._content = harvest_images_in_fragment(instance._content, instance.settings)

    if hasattr(instance, 'metadata'):
        for tag in iter(instance.metadata):
            fragment = getattr(instance, tag)
            if isinstance(fragment, six.string_types):
                fragment = harvest_images_in_fragment(fragment, instance.settings)
                setattr(instance, tag.lower(), fragment)
                instance.metadata[tag] = fragment


def harvest_images_in_fragment(fragment, settings):
    fragment_changed = False
    soup = BeautifulSoup(fragment)

    for img in soup.find_all('img', class_=re.compile("image-process-[-a-zA-Z0-9_]+")):
        for c in img['class']:
            match = re.search(r"image-process-([-a-zA-Z0-9_]+)", c)
            if match is not None:
                derivative = match.group(1)

                if derivative not in settings['IMAGE_PROCESS']:
                    raise RuntimeError('Derivative %s undefined.' % (derivative,))

                if isinstance(settings['IMAGE_PROCESS'][derivative], dict) and \
                        'type' not in settings['IMAGE_PROCESS'][derivative]:
                    raise RuntimeError('"type" is mandatory for %s.' % derivative)

                if isinstance(settings['IMAGE_PROCESS'][derivative], list) or \
                        (isinstance(settings['IMAGE_PROCESS'][derivative], dict) and \
                             settings['IMAGE_PROCESS'][derivative]['type'] == 'image'):

                    # Single source image specification.
                    process_img_tag(img, settings, derivative)
                    fragment_changed = True

                elif isinstance(settings['IMAGE_PROCESS'][derivative], dict) and \
                        settings['IMAGE_PROCESS'][derivative]['type'] == 'responsive-image':

                    # srcset image specification.
                    build_srcset(img, settings, derivative)
                    fragment_changed = True

                elif isinstance(settings['IMAGE_PROCESS'][derivative], dict) and \
                        settings['IMAGE_PROCESS'][derivative]['type'] == 'picture':

                    # Multiple source (picture) specification.
                    group = img.find_parent()
                    if group.name == 'div':
                        convert_div_to_picture_tag(soup, img, group, settings, derivative)
                    elif group.name == 'picture':
                        process_picture(soup, img, group, settings, derivative)
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


def process_img_tag(img, settings, derivative):
    url_path, filename = os.path.split(img['src'])
    base_url = os.path.join(url_path, settings['IMAGE_PROCESS_DIR'], derivative)

    source = os.path.join(settings['PATH'], img['src'][1:])
    output_path, _ = os.path.split(source)
    base_path = os.path.join(output_path, settings['IMAGE_PROCESS_DIR'], derivative)

    img['src'] = os.path.join(base_url, filename)
    destination = os.path.join(base_path, filename)
    if isinstance(settings['IMAGE_PROCESS'][derivative], list):
        process = settings['IMAGE_PROCESS'][derivative]
    else:
        process = settings['IMAGE_PROCESS'][derivative]['ops']
    images.append((source, destination, process))


def build_srcset(img, settings, derivative):
    url_path, filename = os.path.split(img['src'])
    base_url = os.path.join(url_path, settings['IMAGE_PROCESS_DIR'], derivative)

    source = os.path.join(settings['PATH'], img['src'][1:])
    output_path, _ = os.path.split(source)
    base_path = os.path.join(output_path, settings['IMAGE_PROCESS_DIR'], derivative)

    default = settings['IMAGE_PROCESS'][derivative]['default']
    if isinstance(default, six.string_types):
        default_name = default
    elif isinstance(default, list):
        default_name = 'default'
        destination = os.path.join(base_path, default_name, filename)
        images.append((source, destination, default))

    img['src'] = os.path.join(base_url, default_name, filename)

    if 'sizes' in settings['IMAGE_PROCESS'][derivative]:
        img['sizes'] = settings['IMAGE_PROCESS'][derivative]['sizes']

    srcset = []
    for src in settings['IMAGE_PROCESS'][derivative]['srcset']:
        srcset.append("%s %s" % (os.path.join(base_url, src[0], filename),
                                 src[0]))
        destination = os.path.join(base_path, src[0], filename)
        images.append((source, destination, src[1]))

    if len(srcset) > 0:
        img['srcset'] = ', '.join(srcset)


def convert_div_to_picture_tag(soup, img, group, settings, derivative):
    """
    Convert a div containing multiple images to a picture.
    """
    url_path, filename = os.path.split(img['src'])
    base_url = os.path.join(url_path, settings['IMAGE_PROCESS_DIR'], derivative)

    source = os.path.join(settings['PATH'], img['src'][1:])
    output_path, _ = os.path.split(source)
    base_path = os.path.join(output_path, settings['IMAGE_PROCESS_DIR'], derivative)

    # Compile sources URL. Special source "default" uses the main
    # image URL. Other sources use the img with classes
    # [source['name'], 'image-process'].  We also remove the img from
    # the DOM.
    sources = copy.deepcopy(settings['IMAGE_PROCESS'][derivative]['sources'])
    for s in sources:
        if s['name'] == 'default':
            s['url'] = img['src']
        else:
            candidates = group.find_all('img', class_=s['name'])
            for candidate in candidates:
                if 'image-process' in candidate['class']:
                    s['url'] = candidate['src']
                    candidate.decompose()
                    break

        url_path, s['filename'] = os.path.split(s['url'])
        s['base_url'] = os.path.join(url_path, settings['IMAGE_PROCESS_DIR'], derivative)

        source = os.path.join(settings['PATH'], s['url'][1:])
        output_path, _ = os.path.split(source)
        s['base_path'] = os.path.join(output_path, settings['IMAGE_PROCESS_DIR'], derivative)

    # If default is not None, change default img source to the image
    # derivative referenced.
    default = settings['IMAGE_PROCESS'][derivative]['default']
    if default is not None:
        default_source_name = default[0]

        default_source = None
        for s in sources:
            if s['name'] == default_source_name:
                default_source = s
                break

        if default_source is None:
            raise RuntimeError('No source matching "%s", referenced in default setting.',
                               (default_source_name,))

        if isinstance(default[1], six.string_types):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = 'default'

            source = os.path.join(settings['PATH'], default_source['url'][1:])
            destination = os.path.join(s['base_path'], default_source_name,
                                       default_item_name, default_source['filename'])
            images.append((source, destination, default[1]))

        # Change img src to url of default processed image.
        img['src'] = os.path.join(s['base_url'], default_source_name, default_item_name,
                                  default_source['filename'])

    # Create picture tag.
    picture_tag = soup.new_tag('picture')
    for s in sources:
        # Create new <source>
        source_attrs = {k:s[k] for k in s if k in ['media', 'sizes']}
        source_tag = soup.new_tag('source', **source_attrs)

        srcset = []
        for src in s['srcset']:
            srcset.append("%s %s" % (os.path.join(s['base_url'], s['name'], src[0], s['filename']),
                                     src[0]))

            source = os.path.join(settings['PATH'], s['url'][1:])
            destination = os.path.join(s['base_path'], s['name'], src[0], s['filename'])
            images.append((source, destination, src[1]))

        if len(srcset) > 0:
            source_tag['srcset'] = ', '.join(srcset)

        picture_tag.append(source_tag)

    # Wrap img with <picture>
    img.wrap(picture_tag)


def process_picture(soup, img, group, settings, derivative):
    """
    Convert a simplified picture to a full HTML picture:

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
    # Compile sources URL. Special source "default" uses the main
    # image URL. Other sources use the <source> with classes
    # source['name'].  We also remove the <source>s from the DOM.
    sources = copy.deepcopy(settings['IMAGE_PROCESS'][derivative]['sources'])
    for s in sources:
        if s['name'] == 'default':
            s['url'] = img['src']
            source_attrs = {k:s[k] for k in s if k in ['media', 'sizes']}
            s['element'] = soup.new_tag('source', **source_attrs)
        else:
            s['element'] = group.find('source', class_=s['name']).extract()
            s['url'] = s['element']['src']
            del s['element']['src']
            del s['element']['class']

        url_path, s['filename'] = os.path.split(s['url'])
        s['base_url'] = os.path.join(url_path, settings['IMAGE_PROCESS_DIR'], derivative)

        source = os.path.join(settings['PATH'], s['url'][1:])
        output_path, _ = os.path.split(source)
        s['base_path'] = os.path.join(output_path, settings['IMAGE_PROCESS_DIR'], derivative)

    # If default is not None, change default img source to the image
    # derivative referenced.
    default = settings['IMAGE_PROCESS'][derivative]['default']
    if default is not None:
        default_source_name = default[0]

        default_source = None
        for s in sources:
            if s['name'] == default_source_name:
                default_source = s
                break

        if default_source is None:
            raise RuntimeError('No source matching "%s", referenced in default setting.',
                               (default_source_name,))

        if isinstance(default[1], six.string_types):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = 'default'

            source = os.path.join(settings['PATH'], default_source['url'][1:])
            destination = os.path.join(s['base_path'], default_source_name,
                                       default_item_name, default_source['filename'])
            images.append((source, destination, default[1]))


        # Change img src to url of default processed image.
        img['src'] = os.path.join(s['base_url'], default_source_name, default_item_name,
                                  default_source['filename'])

    # Generate srcsets and put back <source>s in <picture>.
    for s in sources:
        srcset = []
        for src in s['srcset']:
            srcset.append("%s %s" % (os.path.join(s['base_url'], s['name'], src[0], s['filename']),
                                     src[0]))

            source = os.path.join(settings['PATH'], s['url'][1:])
            destination = os.path.join(s['base_path'], s['name'], src[0], s['filename'])
            images.append((source, destination, src[1]))

        if len(srcset) > 0:
            # Append source elements to the picture in the same order
            # as they are found in
            # settings['IMAGE_PROCESS'][derivative]['sources'].
            s['element']['srcset'] = ', '.join(srcset)
            img.insert_before(s['element'])


def process_images(p):
    # Set default value for 'IMAGE_PROCESS_FORCE'.
    if 'IMAGE_PROCESS_FORCE' not in p.settings:
        p.settings['IMAGE_PROCESS_FORCE'] = False

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
        if (p.settings['IMAGE_PROCESS_FORCE']) or \
                (not os.path.exists(image[1])) or \
                (os.path.getmtime(image[0]) > os.path.getmtime(image[1])):

            i = Image.open(image[0])

            for step in image[2]:
                if hasattr(step, '__call__'):
                    i = step(i)
                else:
                    elems = step.split(' ')
                    i = basic_ops[elems[0]](i, *(elems[1:]))

            i.save(image[1])

    # Clean up images global for the case where Pelican is running in
    # autoreload mode.
    del images[:]


def register():
    signals.content_object_init.connect(harvest_images)
    signals.finalized.connect(process_images)
