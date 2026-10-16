SELLER_GROUP = "продавец"


def can_upload_boards(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user.groups.filter(name=SELLER_GROUP).exists()


def can_edit_catalog(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.is_staff and user.has_perm("catalog.change_receiver")
