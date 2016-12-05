# -*- coding: utf-8 -*- #
"""
Image Process
=============

This plugin process images according to their class attribute.
"""
from __future__ import unicode_literals

import copy
import collections
import functools
import os.path
import re
import six
import logging

from PIL import Image, ImageFilter
from bs4 import BeautifulSoup
from pelican import signals

logger = logging.getLogger(__name__)

IMAGE_PROCESS_REGEX = re.compile("image-process-[-a-zA-Z0-9_]+")

Path = collections.namedtuple(
    'Path', ['base_url', 'source', 'base_path', 'filename', 'process_dir']
)


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

    return (t, l, r, b)


def crop(i, t, l, r, b):
    """Crop image i to the box (l,t)-(r,b).

    t, l, r, b (top, left, right, bottom) must be strings specifying
    either a number or a percentage.
    """
    t, l, r, b = convert_box(i, t, l, r, b)
    return i.crop((int(t), int(l), int(r), int(b)))


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

    return i.resize((int(w), int(h)), Image.LANCZOS)


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
    'edge_enhance': functools.partial(apply_filter,
                                      f=ImageFilter.EDGE_ENHANCE),
    'edge_enhance_more': functools.partial(apply_filter,
                                           f=ImageFilter.EDGE_ENHANCE_MORE),
    'emboss': functools.partial(apply_filter, f=ImageFilter.EMBOSS),
    'find_edges': functools.partial(apply_filter, f=ImageFilter.FIND_EDGES),
    'smooth': functools.partial(apply_filter, f=ImageFilter.SMOOTH),
    'smooth_more': functools.partial(apply_filter, f=ImageFilter.SMOOTH_MORE),
    'sharpen': functools.partial(apply_filter, f=ImageFilter.SHARPEN),
}


def harvest_images(path, context):
    # Set default value for 'IMAGE_PROCESS_DIR'.
    if 'IMAGE_PROCESS_DIR' not in context:
        context['IMAGE_PROCESS_DIR'] = 'derivatives'

    with open(path, 'r+') as f:
        res = harvest_images_in_fragment(f, context)
        f.seek(0)
        f.truncate()
        f.write(res)


def for_all_nodes(soup, selector, clbk):
    find_tags = None
    if isinstance(selector, six.string_types):
        find_tags = functools.partial(BeautifulSoup.select, soup, selector)
    elif isinstance(selector, dict):
        find_tags = functools.partial(BeautifulSoup.find_all, soup, **selector)
    else:
        find_tags = functools.partial(BeautifulSoup.find_all, soup, selector)

    for tag in find_tags():
        clbk(soup, tag)


def soup_selector(name, proc_spec=None):
    proc_spec = proc_spec or {}
    return proc_spec.get('selector', {
        'attrs': {
            'class': 'image-process-{}'.format(name)
        }
    })


def harvest_images_in_fragment(fragment, settings):
    parser = settings.get("IMAGE_PROCESS_PARSER", "html.parser")
    soup = BeautifulSoup(fragment, parser)

    for derivative, proc_spec in settings['IMAGE_PROCESS'].iteritems():
        if isinstance(proc_spec, list):
            # Single source image specification, simple format
            proc_spec = {
                'type': 'image',
                'ops': proc_spec
            }

        if not isinstance(proc_spec, dict):
            raise RuntimeError('Derivative %s definition not handled'
                               '(must be list or dict)' % (derivative))

        if 'type' not in proc_spec:
            raise RuntimeError('"type" is mandatory for %s.' % derivative)

        d_type = proc_spec['type']
        if 'image' == d_type:
            selector = soup_selector(derivative, proc_spec)
            for_all_nodes(soup, selector,
                          functools.partial(process_tag_replace,
                                            settings=settings,
                                            derivative=derivative,
                                            proc_spec=proc_spec))

        elif 'responsive-image' == d_type:
            selector = soup_selector(derivative, proc_spec)
            for_all_nodes(soup, selector,
                          functools.partial(build_srcset,
                                            settings=settings,
                                            derivative=derivative,
                                            proc_spec=proc_spec))

        elif 'picture' == d_type:
            selector = soup_selector(derivative, proc_spec)
            for_all_nodes(soup, selector,
                          functools.partial(process_or_convert_picture,
                                            settings=settings,
                                            derivative=derivative,
                                            proc_spec=proc_spec))

    return str(soup)


def get_image_path(tag, proc_spec):
    src_spec = proc_spec.get('src', {})

    attr_name = src_spec.get('attribute', 'src')
    path = tag[attr_name]

    path_re = src_spec.get('path-regex', None)
    if path_re:
        m = re.match(path_re, path)
        if m and m.lastindex:
            return m.group(m.lastindex)
        return

    return path


def set_image_path(tag, url, proc_spec):
    dst_spec = proc_spec.get('dst', {})

    fmt = dst_spec.get('format', '{}')
    val = fmt.format(url)

    attr_name = dst_spec.get('attribute', 'src')
    tag[attr_name] = val


def compute_paths(tag, settings, derivative, proc_spec):
    process_dir = settings['IMAGE_PROCESS_DIR']
    img_path = get_image_path(tag, proc_spec)
    if not img_path:
        logger.warn('can not find image src path for tag: %s', tag)
        return

    url_path, filename = os.path.split(img_path)
    base_url = os.path.join(url_path, process_dir, derivative)

    for f in settings['filenames']:
        if os.path.basename(img_path) in f:
            source = settings['filenames'][f].source_path
            base_path = os.path.join(
                settings['OUTPUT_PATH'],
                os.path.dirname(settings['filenames'][f].save_as),
                process_dir,
                derivative)
            break
    else:
        source = os.path.join(settings['PATH'], img_path[1:])
        base_path = os.path.join(settings['OUTPUT_PATH'], base_url[1:])

    return Path(base_url, source, base_path, filename, process_dir)


def process_tag_replace(soup, tag, settings, derivative, proc_spec):
    path = compute_paths(tag, settings, derivative, proc_spec)
    if not path:
        return

    image_url = os.path.join(path.base_url, path.filename)
    set_image_path(tag, image_url, proc_spec)

    process = proc_spec['ops']
    destination = os.path.join(path.base_path, path.filename)
    process_image((path.source, destination, process), settings)


def build_srcset(soup, tag, settings, derivative, proc_spec):
    path = compute_paths(tag, settings, derivative, proc_spec)
    if not path:
        return

    default = proc_spec['default']
    if isinstance(default, six.string_types):
        default_name = default
    elif isinstance(default, list):
        default_name = 'default'
        destination = os.path.join(path.base_path, default_name, path.filename)
        process_image((path.source, destination, default), settings)

    image_url = os.path.join(path.base_url, default_name, path.filename)
    set_image_path(tag, image_url, proc_spec)

    if 'sizes' in proc_spec:
        tag['sizes'] = proc_spec['sizes']

    srcset = []
    for src in proc_spec['srcset']:
        file_path = os.path.join(path.base_url, src[0], path.filename)
        srcset.append("%s %s" % (file_path, src[0]))
        destination = os.path.join(path.base_path, src[0], path.filename)
        process_image((path.source, destination, src[1]), settings)

    if len(srcset) > 0:
        tag['srcset'] = ', '.join(srcset)


def process_or_convert_picture(soup, tag, settings, derivative, proc_spec):
    # Multiple source (picture) specification.
    group = tag.find_parent()
    if group.name == 'div':
        convert_div_to_picture_tag(soup, tag, group, settings, derivative)
    elif group.name == 'picture':
        process_picture(soup, tag, group, settings, derivative)


def convert_div_to_picture_tag(soup, img, group, settings, derivative):
    """
    Convert a div containing multiple images to a picture.
    """
    process_dir = settings['IMAGE_PROCESS_DIR']
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
        s['base_url'] = os.path.join(url_path, process_dir, derivative)
        s['base_path'] = os.path.join(settings['OUTPUT_PATH'],
                                      s['base_url'][1:])

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
            raise RuntimeError(
                'No source matching "%s", referenced in default setting.',
                (default_source_name,)
            )

        if isinstance(default[1], six.string_types):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = 'default'

            source = os.path.join(settings['PATH'], default_source['url'][1:])
            destination = os.path.join(s['base_path'], default_source_name,
                                       default_item_name,
                                       default_source['filename'])
            process_image((source, destination, default[1]), settings)

        # Change img src to url of default processed image.
        img['src'] = os.path.join(s['base_url'], default_source_name,
                                  default_item_name,
                                  default_source['filename'])

    # Create picture tag.
    picture_tag = soup.new_tag('picture')
    for s in sources:
        # Create new <source>
        source_attrs = {k: s[k] for k in s if k in ['media', 'sizes']}
        source_tag = soup.new_tag('source', **source_attrs)

        srcset = []
        for src in s['srcset']:
            srcset.append("%s %s" % (os.path.join(s['base_url'], s['name'],
                                     src[0], s['filename']), src[0]))

            source = os.path.join(settings['PATH'], s['url'][1:])
            destination = os.path.join(s['base_path'], s['name'], src[0],
                                       s['filename'])
            process_image((source, destination, src[1]), settings)

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

    process_dir = settings['IMAGE_PROCESS_DIR']
    process = settings['IMAGE_PROCESS'][derivative]
    # Compile sources URL. Special source "default" uses the main
    # image URL. Other sources use the <source> with classes
    # source['name'].  We also remove the <source>s from the DOM.
    sources = copy.deepcopy(process['sources'])
    for s in sources:
        if s['name'] == 'default':
            s['url'] = img['src']
            source_attrs = {k: s[k] for k in s if k in ['media', 'sizes']}
            s['element'] = soup.new_tag('source', **source_attrs)
        else:
            s['element'] = group.find('source', class_=s['name']).extract()
            s['url'] = s['element']['src']
            del s['element']['src']
            del s['element']['class']

        url_path, s['filename'] = os.path.split(s['url'])
        s['base_url'] = os.path.join(url_path, process_dir, derivative)
        s['base_path'] = os.path.join(settings['OUTPUT_PATH'],
                                      s['base_url'][1:])

    # If default is not None, change default img source to the image
    # derivative referenced.
    default = process['default']
    if default is not None:
        default_source_name = default[0]

        default_source = None
        for s in sources:
            if s['name'] == default_source_name:
                default_source = s
                break

        if default_source is None:
            raise RuntimeError(
                'No source matching "%s", referenced in default setting.',
                (default_source_name,)
            )

        if isinstance(default[1], six.string_types):
            default_item_name = default[1]

        elif isinstance(default[1], list):
            default_item_name = 'default'
            source = os.path.join(settings['PATH'], default_source['url'][1:])
            destination = os.path.join(s['base_path'], default_source_name,
                                       default_item_name,
                                       default_source['filename'])

            process_image((source, destination, default[1]), settings)

        # Change img src to url of default processed image.
        img['src'] = os.path.join(s['base_url'], default_source_name,
                                  default_item_name,
                                  default_source['filename'])

    # Generate srcsets and put back <source>s in <picture>.
    for s in sources:
        srcset = []
        for src in s['srcset']:
            srcset.append("%s %s" % (os.path.join(s['base_url'], s['name'],
                                     src[0], s['filename']), src[0]))

            source = os.path.join(settings['PATH'], s['url'][1:])
            destination = os.path.join(s['base_path'], s['name'], src[0],
                                       s['filename'])
            process_image((source, destination, src[1]), settings)

        if len(srcset) > 0:
            # Append source elements to the picture in the same order
            # as they are found in
            # settings['IMAGE_PROCESS'][derivative]['sources'].
            s['element']['srcset'] = ', '.join(srcset)
            img.insert_before(s['element'])


def process_image(image, settings):
    # Set default value for 'IMAGE_PROCESS_FORCE'.
    if 'IMAGE_PROCESS_FORCE' not in settings:
        settings['IMAGE_PROCESS_FORCE'] = False

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
    logger.debug('processing image: %s', image[0])
    if (settings['IMAGE_PROCESS_FORCE'] or
        not os.path.exists(image[1]) or
            os.path.getmtime(image[0]) > os.path.getmtime(image[1])):

        i = Image.open(image[0])

        for step in image[2]:
            if hasattr(step, '__call__'):
                i = step(i)
            else:
                elems = step.split(' ')
                i = basic_ops[elems[0]](i, *(elems[1:]))

        i.save(image[1])


def register():
    signals.content_written.connect(harvest_images)
