from django.apps import AppConfig


class NetworkConfig(AppConfig):
    # The source package is named ``tabi``; ``network`` remains the Django
    # app label so the existing migration/database history is preserved.
    name = 'tabi'
    label = 'network'
    verbose_name = 'Tabi'
