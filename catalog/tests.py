from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.management.commands.seed_catalog import parse_bands
from catalog.models import Article, Band, Chip, ChipType, PCBFile, Receiver, ReceiverCategory
from catalog.permissions import SELLER_GROUP, can_edit_catalog, can_upload_boards


class PCBUploadTests(TestCase):
    def setUp(self):
        self.category = ReceiverCategory.objects.create(
            name="п/п носимые",
            short_name="п/п носимые",
            slug="pp-nosimye",
            code="pp",
            is_visible=True,
        )
        self.vega_341 = Receiver.objects.create(name="Вега-341", slug="vega-341", category=self.category)
        self.vega_241 = Receiver.objects.create(name="Вега РП-241-1/2", slug="vega-rp-241", category=self.category)
        unch, _ = ChipType.objects.get_or_create(name="УНЧ", defaults={"sort_order": 10})
        self.chip, _ = Chip.objects.get_or_create(name="К174УН7", defaults={"chip_type": unch})
        if not self.chip.chip_type_id:
            self.chip.chip_type = unch
            self.chip.save(update_fields=["chip_type"])
        Group.objects.get_or_create(name=SELLER_GROUP)
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin")
        self.seller = User.objects.create_user("seller", "seller@example.com", "seller")
        self.seller.groups.add(Group.objects.get(name=SELLER_GROUP))
        self.buyer = User.objects.create_user("buyer", "buyer@example.com", "buyer")

    def test_roles(self):
        self.assertTrue(can_upload_boards(self.admin))
        self.assertTrue(can_upload_boards(self.seller))
        self.assertFalse(can_upload_boards(self.buyer))

    def test_list_hides_upload_for_guests(self):
        response = self.client.get(reverse("catalog:pcb_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Добавить проект")

    def test_seller_sees_upload_and_can_create(self):
        self.client.login(username="seller", password="seller")
        self.assertContains(self.client.get(reverse("catalog:pcb_list")), "Добавить проект")
        payload = {
            "title": "Плата Вега 241/341",
            "kind": PCBFile.Kind.MODERN,
            "version": "1.0",
            "developed_at": timezone.localdate().isoformat(),
            "notes": "Общий размер платы",
            "receivers": [self.vega_241.pk, self.vega_341.pk],
            "chips": [self.chip.pk],
            "file": SimpleUploadedFile("vega.lay", build_lay5(lay_object(6, width=50, points=[(0, 0), (1000, 0)]), 1, 0), content_type="application/octet-stream"),
        }
        response = self.client.post(reverse("catalog:pcb_create"), payload)
        self.assertEqual(response.status_code, 302)
        pcb = PCBFile.objects.get(title="Плата Вега 241/341")
        self.assertEqual(set(pcb.receivers.values_list("name", flat=True)), {"Вега-341", "Вега РП-241-1/2"})
        self.assertEqual(list(pcb.chips.values_list("name", flat=True)), ["К174УН7"])
        self.assertEqual(pcb.created_by, self.seller)
        self.assertEqual(pcb.developed_at, timezone.localdate())
        listing = self.client.get(reverse("catalog:pcb_list")).content.decode()
        self.assertLess(listing.find("Вега-341"), listing.find("Плата Вега 241/341"))
        detail = self.client.get(pcb.get_absolute_url())
        self.assertContains(detail, "Вега-341")
        self.assertContains(detail, "К174УН7")

    def test_third_party_source_and_registered_author(self):
        self.client.login(username="seller", password="seller")
        payload = {
            "title": "Плата с форума",
            "kind": PCBFile.Kind.MODERN,
            "developed_at": timezone.localdate().isoformat(),
            "receivers": [self.vega_341.pk],
            "source_url": "https://example.com/vega-un4",
            "author_name": "seller",
            "file": SimpleUploadedFile("vega.lay", build_lay5(lay_object(6, width=50, points=[(0, 0), (1000, 0)]), 1, 0), content_type="application/octet-stream"),
        }
        response = self.client.post(reverse("catalog:pcb_create"), payload)
        self.assertEqual(response.status_code, 302)
        pcb = PCBFile.objects.get(title="Плата с форума")
        self.assertEqual(pcb.source_url, "https://example.com/vega-un4")
        self.assertEqual(pcb.author_name, "seller")
        self.assertEqual(pcb.author, self.seller)
        detail = self.client.get(pcb.get_absolute_url())
        self.assertContains(detail, "https://example.com/vega-un4")
        self.assertContains(detail, "seller")
        self.assertContains(detail, "на сайте")

    def test_unknown_author_stays_as_nickname(self):
        self.client.login(username="seller", password="seller")
        payload = {
            "title": "Чужая плата",
            "kind": PCBFile.Kind.ORIGINAL,
            "developed_at": timezone.localdate().isoformat(),
            "receivers": [self.vega_341.pk],
            "author_name": "UA3XYZ",
            "file": SimpleUploadedFile("old.lay", build_lay5(lay_object(6, width=50, points=[(0, 0), (1000, 0)]), 1, 0), content_type="application/octet-stream"),
        }
        self.client.post(reverse("catalog:pcb_create"), payload)
        pcb = PCBFile.objects.get(title="Чужая плата")
        self.assertEqual(pcb.author_name, "UA3XYZ")
        self.assertIsNone(pcb.author_id)
        detail = self.client.get(pcb.get_absolute_url())
        self.assertContains(detail, "UA3XYZ")
        self.assertNotContains(detail, "на сайте")

    def test_photos_show_in_carousel(self):
        from io import BytesIO
        from PIL import Image

        def jpeg(name):
            buf = BytesIO()
            Image.new("RGB", (12, 12), (180, 140, 70)).save(buf, "JPEG")
            return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

        self.client.login(username="seller", password="seller")
        payload = {
            "title": "Плата с фото",
            "kind": PCBFile.Kind.MODERN,
            "developed_at": timezone.localdate().isoformat(),
            "receivers": [self.vega_341.pk],
            "file": SimpleUploadedFile("board.lay", build_lay5(lay_object(6, width=50, points=[(0, 0), (1000, 0)]), 1, 0), content_type="application/octet-stream"),
            "photos": [jpeg("one.jpg"), jpeg("two.jpg")],
        }
        response = self.client.post(reverse("catalog:pcb_create"), payload)
        self.assertEqual(response.status_code, 302)
        pcb = PCBFile.objects.get(title="Плата с фото")
        self.assertEqual(pcb.photos.count(), 2)
        detail = self.client.get(pcb.get_absolute_url())
        self.assertContains(detail, "data-carousel")
        self.assertContains(detail, "carousel.js")
        listing = self.client.get(reverse("catalog:pcb_list"))
        self.assertContains(listing, pcb.photos.first().image.url)

    def test_buyer_cannot_open_form(self):
        self.client.login(username="buyer", password="buyer")
        self.assertEqual(self.client.get(reverse("catalog:pcb_create")).status_code, 403)


class DocumentViewerTests(TestCase):
    def setUp(self):
        self.category = ReceiverCategory.objects.create(
            name="п/п носимые",
            short_name="п/п носимые",
            slug="pp-nosimye",
            code="pp",
            is_visible=True,
        )
        self.receiver = Receiver.objects.create(
            name="Вега-341-1",
            slug="vega-341-1",
            category=self.category,
            board_drawing=SimpleUploadedFile("schema.pdf", b"%PDF-1.1", content_type="application/pdf"),
            manual=SimpleUploadedFile("ins.djvu", b"AT&TFORM", content_type="image/vnd.djvu"),
        )

    def test_receiver_opens_manual_in_viewer(self):
        page = self.client.get(self.receiver.get_absolute_url())
        self.assertContains(page, "Инструкция")
        self.assertNotContains(page, 'class="doc-frame"')
        self.assertNotContains(page, "data-djvu-url")
        manual = self.client.get(
            reverse("catalog:receiver_manual", args=[self.category.slug, self.receiver.slug])
        )
        self.assertContains(manual, "data-djvu-url")
        self.assertContains(manual, "vendor/djvu/djvu.js")
        drawing = self.client.get(
            reverse("catalog:receiver_drawing", args=[self.category.slug, self.receiver.slug])
        )
        self.assertContains(drawing, 'class="doc-frame"')

    def test_receiver_opens_jpg_drawing_in_viewer(self):
        self.receiver.board_drawing = SimpleUploadedFile(
            "schema.jpg", b"\xff\xd8\xff\xd9", content_type="image/jpeg"
        )
        self.receiver.save()
        page = self.client.get(self.receiver.get_absolute_url())
        self.assertContains(page, "Рисунок платы")
        self.assertNotContains(page, 'class="receiver-photo"')
        drawing = self.client.get(
            reverse("catalog:receiver_drawing", args=[self.category.slug, self.receiver.slug])
        )
        self.assertContains(drawing, "doc-image")
        self.assertContains(drawing, self.receiver.board_drawing.url)

    def test_article_opens_original_in_viewer(self):
        article = Article.objects.create(
            title="Схема Веги",
            slug="skhema-vegi",
            published_at=timezone.localdate(),
            original_file=SimpleUploadedFile("article.pdf", b"%PDF-1.1", content_type="application/pdf"),
        )
        page = self.client.get(article.get_absolute_url())
        self.assertContains(page, "Оригинал")
        self.assertNotContains(page, 'class="doc-frame"')
        viewer = self.client.get(reverse("catalog:article_original", args=[article.slug]))
        self.assertContains(viewer, 'class="doc-frame"')

    def test_article_opens_jpg_in_viewer(self):
        article = Article.objects.create(
            title="Скан схемы",
            slug="skan-skhemy",
            published_at=timezone.localdate(),
            original_file=SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff\xd9", content_type="image/jpeg"),
        )
        page = self.client.get(article.get_absolute_url())
        self.assertContains(page, "Оригинал")
        viewer = self.client.get(reverse("catalog:article_original", args=[article.slug]))
        self.assertContains(viewer, "doc-image")


class ReceiverEditTests(TestCase):
    def setUp(self):
        self.category = ReceiverCategory.objects.create(
            name="п/п носимые",
            short_name="п/п носимые",
            slug="pp-nosimye",
            code="pp",
            is_visible=True,
        )
        self.receiver = Receiver.objects.create(
            name="Вега-341",
            slug="vega-341",
            category=self.category,
            description="Старое описание",
        )
        Group.objects.get_or_create(name=SELLER_GROUP)
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin")
        self.seller = User.objects.create_user("seller", "seller@example.com", "seller")
        self.seller.groups.add(Group.objects.get(name=SELLER_GROUP))
        self.buyer = User.objects.create_user("buyer", "buyer@example.com", "buyer")
        self.staff = User.objects.create_user("staff", "staff@example.com", "staff", is_staff=True)
        self.edit_url = reverse("catalog:receiver_edit", args=[self.category.slug, self.receiver.slug])
        self.admin_url = reverse("admin:catalog_receiver_change", args=[self.receiver.pk])

    def test_roles(self):
        self.assertTrue(can_edit_catalog(self.admin))
        self.assertFalse(can_edit_catalog(self.seller))
        self.assertFalse(can_edit_catalog(self.buyer))
        self.assertFalse(can_edit_catalog(self.staff))

    def test_guest_does_not_see_edit_tab(self):
        page = self.client.get(self.receiver.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Редактирование")
        self.assertNotContains(page, self.edit_url)

    def test_guest_cannot_open_edit(self):
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_seller_and_buyer_cannot_open_edit(self):
        self.client.login(username="seller", password="seller")
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)
        self.client.login(username="buyer", password="buyer")
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)
        self.client.login(username="staff", password="staff")
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)

    def test_admin_sees_tabs_and_can_save(self):
        self.client.login(username="admin", password="admin")
        card = self.client.get(self.receiver.get_absolute_url())
        self.assertContains(card, "Карточка")
        self.assertContains(card, "Редактирование")
        self.assertContains(card, self.edit_url)
        form_page = self.client.get(self.edit_url)
        self.assertEqual(form_page.status_code, 200)
        self.assertContains(form_page, "Сохранить карточку")
        response = self.client.post(
            self.edit_url,
            {
                "name": self.receiver.name,
                "slug": self.receiver.slug,
                "category": self.category.pk,
                "description": "Новое описание",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.edit_url)
        self.receiver.refresh_from_db()
        self.assertEqual(self.receiver.description, "Новое описание")

    def test_admin_change_form_has_site_tab(self):
        self.client.login(username="admin", password="admin")
        page = self.client.get(self.admin_url)
        self.assertContains(page, "Запись в админке")
        self.assertContains(page, "Редактирование на сайте")
        self.assertContains(page, self.edit_url)

    def test_staff_can_open_hidden_receiver(self):
        self.receiver.is_hidden = True
        self.receiver.save(update_fields=["is_hidden"])
        self.assertEqual(self.client.get(self.receiver.get_absolute_url()).status_code, 404)
        self.client.login(username="admin", password="admin")
        self.assertEqual(self.client.get(self.receiver.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.edit_url).status_code, 200)


class ReceiverYearsDisplayTests(TestCase):
    def setUp(self):
        self.category = ReceiverCategory.objects.create(
            name="п/п носимые",
            short_name="п/п носимые",
            slug="pp-nosimye",
            code="pp",
            is_visible=True,
        )

    def test_years_display_formats(self):
        both = Receiver(year_start=1988, year_end=1992)
        self.assertEqual(both.years_display, "1988–1992")
        same = Receiver(year_start=1988, year_end=1988)
        self.assertEqual(same.years_display, "1988")
        start_only = Receiver(year_start=1984)
        self.assertEqual(start_only.years_display, "с 1984")
        end_only = Receiver(year_end=1992)
        self.assertEqual(end_only.years_display, "до 1992")
        empty = Receiver()
        self.assertEqual(empty.years_display, "")

    def test_card_shows_one_year_line_and_produced_count(self):
        receiver = Receiver.objects.create(
            name="Вега-341",
            slug="vega-341",
            category=self.category,
            year_start=1988,
            year_end=1992,
            produced_count=12340,
        )
        page = self.client.get(receiver.get_absolute_url())
        html = page.content.decode()
        self.assertIn("1988–1992", html)
        self.assertRegex(html, r"12[\s\u00a0]340 шт\.")
        self.assertNotIn("Год начала", html)
        self.assertNotIn("Год окончания", html)
        self.assertEqual(html.count("Годы выпуска"), 1)


class BandFMTests(TestCase):
    def test_migration_adds_fm(self):
        band = Band.objects.get(code="FM")
        self.assertEqual(band.name, "FM (87,5–108 МГц)")

    def test_parse_bands_finds_fm(self):
        codes, note = parse_bands("ДВ, УКВ, FM")
        self.assertEqual(codes, ["УКВ", "ДВ", "FM"])
        self.assertEqual(note, "")

    def test_edit_form_lists_fm(self):
        category = ReceiverCategory.objects.create(
            name="п/п носимые",
            short_name="п/п носимые",
            slug="pp-nosimye",
            code="pp",
            is_visible=True,
        )
        receiver = Receiver.objects.create(name="Вега-341", slug="vega-341", category=category)
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin")
        self.client.login(username="admin", password="admin")
        page = self.client.get(reverse("catalog:receiver_edit", args=[category.slug, receiver.slug]))
        self.assertIn("FM</label>", page.content.decode())


def build_lay5(objects_bytes, num_objects, num_pads):
    """Минимальный файл Sprint Layout 5: одна плата 50×30 мм."""
    import struct

    name = "Тест".encode("cp1251")
    header = bytearray(534)
    header[0] = len(name)
    header[1:1 + len(name)] = name
    struct.pack_into("<II", header, 35, 5000, 3000)
    struct.pack_into("<I", header, 530, num_objects)
    trailer = bytes(0x137 - 4) + struct.pack("<I", 0)
    connections = struct.pack("<I", 0) * num_pads
    return b"\x05\x33\xaa\xff" + struct.pack("<I", 1) + bytes(header) + objects_bytes + connections + trailer


def lay_object(kind, x=0.0, y=0.0, out=0.0, inner=0.0, width=0, layer=3, shape=1, points=()):
    import struct

    head = bytearray(77)
    struct.pack_into("<B4fIBBB", head, 0, kind, x, y, out, inner, width, 0, layer, shape)
    body = struct.pack("<III", 0, 0, 0)  # текст, маркер, группы
    if kind != 5:
        body += struct.pack("<I", len(points)) + b"".join(struct.pack("<ff", *p) for p in points)
    return bytes(head) + body


class LayViewerTests(TestCase):
    def setUp(self):
        objects = lay_object(6, width=50, points=[(500, -500), (4500, -500)]) + lay_object(
            2, x=1000, y=-1500, out=100, inner=40
        )
        self.lay_bytes = build_lay5(objects, num_objects=2, num_pads=1)

    def make_pcb(self, content, is_free=True, name="board.lay", **extra):
        return PCBFile.objects.create(
            title="Тестовая плата",
            kind=PCBFile.Kind.MODERN,
            is_free=is_free,
            file=SimpleUploadedFile(name, content),
            **extra,
        )

    def test_parse_and_render_v5(self):
        from catalog import lay

        parsed = lay.parse(self.lay_bytes)
        self.assertEqual(parsed.version, 5)
        board = parsed.boards[0]
        self.assertEqual(board.name, "Тест")
        self.assertEqual([o.type for o in board.objects], [6, 2])
        svg = lay.render_svg(parsed)
        self.assertIn('data-layer="C2"', svg)
        self.assertIn('data-layer="D"', svg)
        # Дорожка 0,5 мм от 5 до 45 мм, площадка Ø2 мм с отверстием Ø0,8 мм
        self.assertIn('d="M5 5L45 5"', svg)
        self.assertIn('stroke-width="0.5"', svg)
        self.assertIn('<circle cx="10" cy="15" r="1"', svg)
        self.assertIn('<circle cx="10" cy="15" r="0.4"/>', svg)

    def test_rejects_broken_files(self):
        from catalog import lay

        for data in (b"LAY", self.lay_bytes[:300], b"\x07\x33\xaa\xff" + self.lay_bytes[4:]):
            with self.assertRaises(lay.LayError):
                lay.parse(data)

    def test_free_board_has_preview_and_viewer(self):
        pcb = self.make_pcb(self.lay_bytes)
        page = self.client.get(pcb.get_absolute_url())
        self.assertContains(page, reverse("catalog:pcb_svg", args=[pcb.pk]))
        svg = self.client.get(reverse("catalog:pcb_svg", args=[pcb.pk]))
        self.assertEqual(svg.status_code, 200)
        self.assertEqual(svg["Content-Type"], "image/svg+xml; charset=utf-8")
        viewer = self.client.get(reverse("catalog:pcb_preview", args=[pcb.pk]))
        self.assertContains(viewer, "data-lay-viewer")
        self.assertContains(viewer, "<svg")

    def test_paid_board_is_not_rendered(self):
        pcb = self.make_pcb(self.lay_bytes, is_free=False)
        self.assertNotContains(self.client.get(pcb.get_absolute_url()), "plata.svg")
        self.assertEqual(self.client.get(reverse("catalog:pcb_svg", args=[pcb.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("catalog:pcb_preview", args=[pcb.pk])).status_code, 404)

    def test_placeholder_file_has_no_preview(self):
        pcb = self.make_pcb(b"LAY")
        self.assertNotContains(self.client.get(pcb.get_absolute_url()), "plata.svg")
        self.assertEqual(self.client.get(reverse("catalog:pcb_svg", args=[pcb.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse("catalog:pcb_preview", args=[pcb.pk])), "Не удалось прочитать")

    def test_lay6_upload_is_allowed(self):
        pcb = self.make_pcb(b"\x06\x33\xaa\xff", name="board.lay6")
        pcb.full_clean()


class PCBFileAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", "s@example.com", "staff", is_staff=True)
        self.owner = User.objects.create_user("owner", "o@example.com", "owner")
        self.stranger = User.objects.create_user("stranger", "x@example.com", "stranger")
        self.paid = PCBFile.objects.create(
            title="Платная",
            kind=PCBFile.Kind.MODERN,
            is_free=False,
            created_by=self.owner,
            file=SimpleUploadedFile("paid.lay", b"SECRET"),
        )
        self.free = PCBFile.objects.create(
            title="Бесплатная",
            kind=PCBFile.Kind.ORIGINAL,
            is_free=True,
            file=SimpleUploadedFile("free.pdf", b"%PDF-1.1"),
        )

    def test_files_are_stored_outside_media(self):
        from pathlib import Path

        from django.conf import settings

        path = Path(self.paid.file.path)
        self.assertTrue(path.is_relative_to(settings.PRIVATE_MEDIA_ROOT))
        self.assertFalse(path.is_relative_to(settings.MEDIA_ROOT))
        self.assertEqual(self.paid.file.url, reverse("catalog:pcb_file", args=[self.paid.file.name]))

    def test_paid_file_hidden_from_guests_and_strangers(self):
        urls = [self.paid.file.url, reverse("catalog:pcb_download", args=[self.paid.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.login(username="stranger", password="stranger")
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_paid_file_open_to_staff_and_owner(self):
        for username in ("staff", "owner"):
            self.client.login(username=username, password=username)
            response = self.client.get(self.paid.file.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"SECRET")
            self.client.logout()

    def test_free_file_served_inline_and_as_download(self):
        inline = self.client.get(self.free.file.url)
        self.assertEqual(inline.status_code, 200)
        self.assertTrue(inline["Content-Disposition"].startswith("inline"))
        download = self.client.get(reverse("catalog:pcb_download", args=[self.free.pk]))
        self.assertTrue(download["Content-Disposition"].startswith("attachment"))

    def test_unknown_file_name_is_404(self):
        self.assertEqual(self.client.get(reverse("catalog:pcb_file", args=["pcb/nope.lay"])).status_code, 404)


class CatalogIndexImportTests(TestCase):
    def run_index(self, items):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock

        from catalog.management.commands import seed_catalog

        lamp, _ = ReceiverCategory.objects.get_or_create(code="lamp", defaults={"name": "Ламповые", "short_name": "Ламповые", "slug": "lamp"})
        radiola, _ = ReceiverCategory.objects.get_or_create(code="rl_lamp", defaults={"name": "Радиолы", "short_name": "Радиолы", "slug": "rl-lamp"})
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "all_catalog.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(seed_catalog, "DATA", Path(tmp)):
                used = set(Receiver.objects.values_list("slug", flat=True))
                seed_catalog.Command()._seed_catalog_index({}, used, {"lamp": lamp, "rl_lamp": radiola})
        return lamp, radiola

    def test_same_name_different_pages_are_separate_models(self):
        base = "https://rw6ase.narod.ru/index1/radiopriem/_rp_lamp/"
        self.run_index([
            {"name": "Ленинград", "category": "lamp", "source_url": base + "leningrad.html"},
            {"name": "Ленинград", "category": "lamp", "source_url": base + "leningrad57.html"},
        ])
        self.assertEqual(Receiver.objects.filter(name="Ленинград").count(), 2)

    def test_one_page_in_two_sections_stays_one_model(self):
        url = "https://rw6ase.narod.ru/index1/radiopriem/rl_lamp/belarus57.html"
        lamp, _ = self.run_index([
            {"name": "Беларусь-57", "category": "lamp", "source_url": url},
            {"name": "Беларусь-57", "category": "rl_lamp", "source_url": url},
        ])
        receiver = Receiver.objects.get(name="Беларусь-57")
        self.assertEqual(receiver.category, lamp)

    def test_rerun_is_idempotent(self):
        items = [{"name": "Байкал", "category": "lamp", "source_url": "https://rw6ase.narod.ru/x/baikal.html"}]
        self.run_index(items)
        self.run_index(items)
        self.assertEqual(Receiver.objects.filter(name="Байкал").count(), 1)


class FrequencyResponseParserTests(TestCase):
    def test_only_audio_band_is_taken(self):
        import sys

        from django.conf import settings

        sys.path.insert(0, str(settings.BASE_DIR))
        from scripts.import_constructors import extract_specs

        self.assertEqual(extract_specs("Полоса частот 300...3500 Гц.").get("frequency_response"), "300...3500 Гц")
        for text in ("Диапазон частот: ДВ 150…405 кГц.", "Диапазон частот от 65,8 до 74 мГц.", "Диапазон принимаемых частот 150 Гц"):
            self.assertNotIn("frequency_response", extract_specs(text), text)


class LayToolsTests(TestCase):
    """Цепи с перемычками, проверка, сравнение версий, запись LAY — на синтетических платах v5."""

    def board(self, objects_spec):
        objs = b"".join(lay_object(**spec) for spec in objects_spec)
        pads = sum(1 for spec in objects_spec if spec["kind"] in (2, 8))
        return build_lay5(objs, len(objects_spec), pads)

    def base_spec(self):
        return [
            dict(kind=2, x=1000, y=-1000, out=100, inner=40),                   # 0: площадка A
            dict(kind=2, x=3000, y=-1000, out=100, inner=40),                   # 1: площадка B
            dict(kind=6, width=50, points=[(1000, -1000), (3000, -1000)]),     # 2: дорожка A—B
            dict(kind=2, x=1000, y=-3000, out=100, inner=40),                   # 3: площадка C
            dict(kind=2, x=3000, y=-3000, out=100, inner=40),                   # 4: площадка D
            dict(kind=6, layer=2, width=20, points=[(1000, -1000), (1000, -3000)]),  # 5: перемычка A—C
        ]

    def test_nets_include_jumpers(self):
        from catalog import lay, laytools

        a = laytools.analyze(lay.parse(self.board(self.base_spec())))
        self.assertEqual(len(a.jumpers), 1)
        self.assertEqual(a.nets[0], a.nets[1])
        self.assertEqual(a.nets[0], a.nets[3])           # через перемычку
        self.assertNotEqual(a.nets[0], a.nets[4])
        self.assertEqual(a.summary["jumpers"], 1)
        self.assertEqual(a.summary["tht_pads"], 4)
        self.assertEqual(dict(a.summary["drills"]), {0.8: 4})
        self.assertEqual(a.issue_counts.get("single"), 1)  # D ни с чем не соединена

    def test_drc_finds_small_clearance(self):
        from catalog import lay, laytools

        spec = self.base_spec()[:3] + [dict(kind=6, width=50, points=[(1500, -1070), (2500, -1070)])]  # зазор 0,2 мм
        a = laytools.analyze(lay.parse(self.board(spec)))
        self.assertGreaterEqual(a.issue_counts.get("clearance", 0), 1)
        self.assertTrue(any(i.kind == "clearance" for i in a.issues))

    def test_diff_detects_split(self):
        from catalog import lay, laytools

        old = lay.parse(self.board(self.base_spec()))
        spec = self.base_spec()
        spec[2] = dict(kind=6, width=50, points=[(1000, -1000), (1500, -1000)])   # дорожку оборвали
        new = lay.parse(self.board(spec))
        d = laytools.diff(old, new)
        self.assertEqual(d.matched, 4)
        self.assertEqual(len(d.splits), 1)
        self.assertEqual(d.merges, [])

    def test_render_marks_nets_and_print(self):
        from catalog import lay, laytools

        parsed = lay.parse(self.board(self.base_spec()))
        a = laytools.analyze(parsed)
        svg = lay.render_svg(parsed, nets=a.nets, markers=a.markers)
        self.assertIn(f'data-net="{a.nets[0]}"', svg)
        self.assertIn('data-layer="E"', svg)
        printed = lay.render_print_svg(parsed, layer=3, mirror=True)
        self.assertIn("scale(-1 1)", printed)
        self.assertIn('fill="#ffffff"', printed)

    def test_layedit_roundtrip(self):
        from catalog.layedit import LayDoc

        data = self.board(self.base_spec())
        doc = LayDoc(data)
        self.assertEqual(doc.to_bytes(), data)
        doc.objects[2].points = [(1000.0, -1000.0), (2000.0, -1000.0)]
        from catalog import lay

        self.assertEqual(lay.parse(doc.to_bytes()).boards[0].objects[2].points[-1], (2000.0, -1000.0))


class LayPagesTests(TestCase):
    def setUp(self):
        spec = LayToolsTests.base_spec(None)
        objs = b"".join(lay_object(**s) for s in spec)
        self.data = build_lay5(objs, len(spec), 4)
        self.owner = User.objects.create_user("owner2", "o2@example.com", "owner2")
        self.free = PCBFile.objects.create(title="Свободная", kind=PCBFile.Kind.MODERN, is_free=True,
                                           created_by=self.owner, file=SimpleUploadedFile("f.lay", self.data))
        self.paid = PCBFile.objects.create(title="Платная", kind=PCBFile.Kind.MODERN, is_free=False,
                                           file=SimpleUploadedFile("p.lay", self.data))

    def test_viewer_has_nets_and_summary(self):
        page = self.client.get(reverse("catalog:pcb_preview", args=[self.free.pk]))
        self.assertContains(page, "data-net=")
        self.assertContains(page, "О плате")
        self.assertNotContains(page, "Замечания проверки")       # гостю — без проверки
        self.client.login(username="owner2", password="owner2")
        page = self.client.get(reverse("catalog:pcb_preview", args=[self.free.pk]))
        self.assertContains(page, "Проверка")
        self.assertContains(page, 'data-layer="E"')

    def test_print_page(self):
        url = reverse("catalog:pcb_print", args=[self.free.pk])
        page = self.client.get(url)
        self.assertContains(page, "50 мм")
        self.assertNotContains(page, "scale(-1 1)")
        self.assertContains(self.client.get(url + "?mirror=1"), "scale(-1 1)")
        self.assertEqual(self.client.get(reverse("catalog:pcb_print", args=[self.paid.pk])).status_code, 404)

    def test_detail_summary_and_list_thumb(self):
        self.assertContains(self.client.get(self.free.get_absolute_url()), "О плате")
        listing = self.client.get(reverse("catalog:pcb_list"))
        self.assertContains(listing, reverse("catalog:pcb_svg", args=[self.free.pk]))
        self.assertNotContains(listing, reverse("catalog:pcb_svg", args=[self.paid.pk]))

    def test_upload_rejects_placeholder_lay(self):
        from catalog.forms import PCBUploadForm

        cat = ReceiverCategory.objects.create(name="К", short_name="К", slug="k", code="k")
        r = Receiver.objects.create(name="Вега", slug="vega-x", category=cat)
        payload = {"title": "Т", "kind": PCBFile.Kind.MODERN, "developed_at": "2026-01-01", "receivers": [r.pk]}
        bad = PCBUploadForm(payload, {"file": SimpleUploadedFile("x.lay", b"LAY")})
        self.assertFalse(bad.is_valid())
        self.assertIn("file", bad.errors)
        good = PCBUploadForm(payload, {"file": SimpleUploadedFile("x.lay", self.data)})
        self.assertTrue(good.is_valid(), good.errors)
