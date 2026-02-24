import os
from io import BytesIO

from PIL import Image
from django.core.files.base import ContentFile


def compress_image(image_field, max_width=1920, max_height=1920, quality=85):
    """
    Сжимает изображение: конвертирует в JPEG, ресайзит если больше лимита.
    Возвращает ContentFile или None если сжатие не нужно.
    """
    if not image_field:
        return None

    try:
        image_field.seek(0)
        img = Image.open(image_field)
    except Exception:
        return None

    # Уже маленький JPEG — не трогаем
    if img.format == 'JPEG' and image_field.size < 200 * 1024:
        return None

    # RGBA/P → RGB (PNG с прозрачностью, палитровые)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Ресайз только если больше лимита
    img.thumbnail((max_width, max_height), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)

    # Новое имя с расширением .jpg
    name = os.path.splitext(os.path.basename(image_field.name))[0] + '.jpg'
    return ContentFile(buf.getvalue(), name=name)
