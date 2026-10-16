from catalog.permissions import can_edit_catalog, can_upload_boards


def permissions(request):
    return {
        "can_upload_boards": can_upload_boards(request.user),
        "can_edit_catalog": can_edit_catalog(request.user),
    }
