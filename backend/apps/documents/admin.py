from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "organization", "status", "chunk_count", "size_bytes", "created_at")
    list_filter = ("status", "organization")
    search_fields = ("original_filename",)
    readonly_fields = [f.name for f in Document._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False
