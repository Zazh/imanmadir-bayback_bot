import os

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image


class Command(BaseCommand):
    help = 'Сжимает все существующие изображения в media/ (Product, TaskStep, StepTemplateItem)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quality', type=int, default=85,
            help='Качество JPEG (по умолчанию 85)',
        )
        parser.add_argument(
            '--max-size', type=int, default=1920,
            help='Максимальный размер стороны в px (по умолчанию 1920)',
        )

    def handle(self, *args, **options):
        quality = options['quality']
        max_size = options['max_size']

        from catalog.models import Product
        from steps.models import TaskStep, StepTemplateItem

        models = [
            (Product, 'image'),
            (TaskStep, 'image'),
            (StepTemplateItem, 'image'),
        ]

        total_saved = 0

        for model_class, field_name in models:
            qs = model_class.objects.exclude(**{field_name: ''})
            count = qs.count()
            if not count:
                continue

            self.stdout.write(f'\n{model_class.__name__}: {count} записей с изображениями')

            for obj in qs:
                image_field = getattr(obj, field_name)
                if not image_field:
                    continue

                try:
                    full_path = image_field.path
                except Exception:
                    continue

                if not os.path.exists(full_path):
                    self.stdout.write(self.style.WARNING(f'  Файл не найден: {full_path}'))
                    continue

                old_size = os.path.getsize(full_path)

                # Пропускаем маленькие JPEG
                try:
                    img = Image.open(full_path)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  Не удалось открыть: {full_path} ({e})'))
                    continue

                if img.format == 'JPEG' and old_size < 200 * 1024:
                    continue

                # Конвертируем
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                img.thumbnail((max_size, max_size), Image.LANCZOS)

                # Сохраняем как JPEG
                new_path = os.path.splitext(full_path)[0] + '.jpg'
                img.save(new_path, format='JPEG', quality=quality, optimize=True)
                new_size = os.path.getsize(new_path)

                # Удаляем старый файл если расширение изменилось
                if new_path != full_path and os.path.exists(full_path):
                    os.remove(full_path)

                # Обновляем путь в БД
                old_name = image_field.name
                new_name = os.path.splitext(old_name)[0] + '.jpg'
                if old_name != new_name:
                    setattr(obj, field_name, new_name)
                    obj._original_image = new_name  # Чтобы save() не сжимал повторно
                    obj.save(update_fields=[field_name])

                saved = old_size - new_size
                total_saved += saved
                self.stdout.write(
                    f'  {os.path.basename(image_field.name)}: '
                    f'{old_size // 1024}KB → {new_size // 1024}KB '
                    f'(сэкономлено {saved // 1024}KB)'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово! Всего сэкономлено: {total_saved // 1024}KB ({total_saved // 1024 // 1024}MB)'
        ))
