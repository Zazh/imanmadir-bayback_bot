# imanmadir-bayback_bot

## Деплой на прод

После `git pull` выполнить:

```bash
# 1. Пересобрать и перезапустить контейнеры
docker compose up -d --build

# 2. Применить миграции (шаблоны шагов)
docker compose exec bayback python manage.py migrate

# 3. Сжать существующие изображения (одноразово)
docker compose exec bayback python manage.py compress_existing_images

# 4. Перезапустить бота чтобы подхватил изменения
docker compose restart bot
```

### Что изменилось

- **Шаблоны шагов** — сохранение шагов задания как шаблон + загрузка при создании нового задания
- **Сжатие изображений** — все загружаемые картинки автоматически конвертируются в JPEG (max 1920px, quality 85)
- **Фикс пустых шагов** — пустые шаги больше не блокируют сохранение формы
