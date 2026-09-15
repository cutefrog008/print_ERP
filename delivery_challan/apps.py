from django.apps import AppConfig


class DeliveryChallanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery_challan'
    verbose_name = 'Delivery Challan'

    def ready(self):
        import delivery_challan.signals  # noqa: F401
