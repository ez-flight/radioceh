from django import template

register = template.Library()

PDF_EXTENSIONS = (".pdf",)
DJVU_EXTENSIONS = (".djvu", ".djv")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
LAY_EXTENSIONS = (".lay", ".lay6")


@register.filter
def file_kind(field):
    name = getattr(field, "name", "") or str(field or "")
    name = name.lower()
    if name.endswith(PDF_EXTENSIONS):
        return "pdf"
    if name.endswith(DJVU_EXTENSIONS):
        return "djvu"
    if name.endswith(IMAGE_EXTENSIONS):
        return "image"
    if name.endswith(LAY_EXTENSIONS):
        return "lay"
    return ""
