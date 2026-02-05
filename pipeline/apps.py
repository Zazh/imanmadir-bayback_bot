from django.apps import AppConfig


class PipelineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pipeline'
    verbose_name = 'Выкупы'

    def ready(self):
        import pipeline.signals  # noqa