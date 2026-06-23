from django.apps import AppConfig # pyright: ignore[reportMissingModuleSource]


class QuizAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quiz_app'
    verbose_name = 'Quiz Application'
