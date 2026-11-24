from django.apps import AppConfig


class StudentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "students"

    def ready(self):  # noqa: D401
        """Enable SQLite WAL for better read/write concurrency in dev."""
        from django.db.backends.signals import connection_created

        def _sqlite_wal(sender, connection, **kwargs):
            if connection.vendor != "sqlite":
                return
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")

        connection_created.connect(_sqlite_wal, dispatch_uid="ums_sqlite_wal")
