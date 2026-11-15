from django.apps import AppConfig


class TabiConfig(AppConfig):
    # Keep the established database app label to preserve existing records.
    name = 'tabi'
    label = 'network'
    verbose_name = 'Tabi'
