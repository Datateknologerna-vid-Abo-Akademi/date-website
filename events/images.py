import logging
import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger('date')

# Background pictures are stored no larger than this on their long edge: a Full HD
# screen's width for landscape pictures, and enough height for portrait posters in
# the sides layout and the phone banner.
BACKGROUND_MAX_EDGE = 1920
# Formats browsers display and that keep their format when resized. Other still
# images (HEIC, TIFF, BMP and the like) become PNG when they have transparency and
# JPEG otherwise.
KEPT_FORMATS = {'JPEG', 'PNG', 'WEBP'}
# Formats whose extra frames are an animation. Pillow's is_animated only means
# "more than one frame": phone JPEGs with an embedded second picture (MPO),
# multi-page TIFFs and multi-image HEIFs report it too, and for those the first
# frame is the picture.
ANIMATED_FORMATS = {'GIF', 'PNG', 'WEBP'}
# Errors Pillow raises for files it cannot decode or modes it cannot process.
# pillow_heif raises RuntimeError when libheif fails to decode a picture.
UNREADABLE = (OSError, SyntaxError, ValueError, RuntimeError, Image.DecompressionBombError)

_SIXTEEN_BIT_MODES = {'I', 'I;16', 'I;16B', 'I;16L', 'I;16N'}
_GREY_MODES = {'L', 'LA', *_SIXTEEN_BIT_MODES}


def _colour_space(mode):
    if mode in _GREY_MODES:
        return 'grey'
    if mode in {'RGB', 'RGBA', 'P', 'PA'}:
        return 'rgb'
    return mode


def _normalise(image):
    """Return ``image`` in a mode every later step and every browser supports.

    The result is RGB, RGBA, L or LA. Transparency, including a palette or colour-key
    transparency entry, becomes an alpha channel.
    """
    if image.mode in _SIXTEEN_BIT_MODES:
        # Wide greyscale: convert() clips every value above 255 to white, so scale down
        # first. 16-bit pictures span 0-65535; a 32-bit picture that goes beyond that
        # is scaled by its brightest pixel.
        wide = image.convert('I')
        brightest = wide.getextrema()[1]
        divisor = 256 if brightest <= 65535 else brightest / 255
        return wide.point(lambda value: value / divisor).convert('L')
    has_alpha = image.mode in {'RGBA', 'LA', 'PA'} or 'transparency' in image.info
    if has_alpha:
        return image if image.mode in {'RGBA', 'LA'} else image.convert('RGBA')
    return image if image.mode in {'RGB', 'L'} else image.convert('RGB')


def _is_lossless_webp(data):
    # A WebP file is a RIFF container whose image chunk is 'VP8L' when lossless and
    # 'VP8 ' when lossy. Pillow does not report which one it read.
    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        if chunk in (b'VP8L', b'VP8 '):
            return chunk == b'VP8L'
        size = int.from_bytes(data[offset + 4 : offset + 8], 'little')
        offset += 8 + size + (size & 1)
    return False


def _dominant_color_of(image):
    """Return the dominant colour of a normalised image as ``#rrggbb``, or ``''``.

    The image is shrunk and reduced to a handful of colours, and the colour that
    covers the most pixels wins. An average would blend, say, a blue sky and a red
    stage into brown. Transparent pixels are skipped so a logo's empty surroundings
    do not count.
    """
    sample = image.copy()
    sample.thumbnail((64, 64))
    pixels = [pixel[:3] for pixel in sample.convert('RGBA').get_flattened_data() if pixel[3] >= 128]
    if not pixels:
        return ''
    flat = Image.new('RGB', (len(pixels), 1))
    flat.putdata(pixels)
    reduced = flat.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    _count, index = max(reduced.getcolors() or [(0, 0)])
    red, green, blue = (reduced.getpalette() or [0, 0, 0])[index * 3 : index * 3 + 3]
    return f'#{red:02x}{green:02x}{blue:02x}'


def process_background_image(uploaded):
    """Prepare an uploaded background picture for storage, reading the file once.

    Returns ``(fitted, colour)``. ``fitted`` is a copy shrunk so its long edge is at
    most ``BACKGROUND_MAX_EDGE`` (a 4032x3024 photo becomes 1920x1440: the shape is
    kept, nothing is cropped or enlarged), or ``None`` when the upload should be
    stored as it is: it already fits, has no EXIF or XMP metadata and is in a kept
    format, it is an animated GIF, PNG or WebP (resizing would drop the animation),
    or Pillow cannot read it.
    Other multi-frame files are processed from their first frame. ``colour`` is the
    picture's dominant colour, or ``''`` when the file cannot be read.
    """
    name = getattr(uploaded, 'name', '') or 'background'
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as image:
            source_format = image.format
            fits = max(image.size) <= BACKGROUND_MAX_EDGE
            animated = getattr(image, 'is_animated', False) and source_format in ANIMATED_FORMATS
            # EXIF (orientation, GPS position, camera serial) and XMP only go away when
            # the picture is re-encoded, so a picture that carries them is never kept as is.
            has_metadata = bool(image.getexif()) or 'xmp' in image.info
            if animated or (fits and not has_metadata and source_format in KEPT_FORMATS):
                return None, _dominant_color_of(_normalise(image))

            # Phones store photos sideways plus an EXIF orientation tag that browsers
            # honour. Re-encoding drops the tag (and the rest of the EXIF data,
            # including any GPS position), so rotate the pixels first.
            fitted = _normalise(ImageOps.exif_transpose(image))
            fitted.thumbnail((BACKGROUND_MAX_EDGE, BACKGROUND_MAX_EDGE), Image.LANCZOS)

            has_alpha = fitted.mode in {'RGBA', 'LA'}
            if source_format in KEPT_FORMATS:
                target_format = source_format
            else:
                target_format = 'PNG' if has_alpha else 'JPEG'
            options = {'optimize': True}
            if target_format in {'JPEG', 'WEBP'}:
                options['quality'] = 85
            if target_format == 'WEBP':
                uploaded.seek(0)
                options['lossless'] = _is_lossless_webp(uploaded.read())
            # Keep the colour profile (iPhone photos are Display P3) unless the pixels
            # changed colour space, for example CMYK converted to RGB.
            icc_profile = image.info.get('icc_profile')
            if icc_profile and _colour_space(image.mode) == _colour_space(fitted.mode):
                options['icc_profile'] = icc_profile

            output = BytesIO()
            fitted.save(output, format=target_format, **options)
            colour = _dominant_color_of(fitted)
    except UNREADABLE as exc:
        logger.warning("Could not process event background image %s: %s", name, exc)
        return None, ''
    finally:
        uploaded.seek(0)

    base, extension = os.path.splitext(os.path.basename(name))
    if target_format != source_format:
        extension = '.png' if target_format == 'PNG' else '.jpg'
    return ContentFile(output.getvalue(), name=f"{base}{extension}"), colour


def dominant_color(picture):
    """Return the dominant colour of a stored or uploaded picture, or ``''``."""
    try:
        picture.seek(0)
        with Image.open(picture) as image:
            return _dominant_color_of(_normalise(image))
    except UNREADABLE as exc:
        logger.warning("Could not read colours of event background image %s: %s", getattr(picture, 'name', ''), exc)
        return ''
    finally:
        picture.seek(0)
