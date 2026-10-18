from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone

from catalog.models import Band, Chip, Factory, PCBFile, Receiver

PHOTO_EXTENSIONS = ("jpg", "jpeg", "png", "webp")


class MultiImageInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        cleaned = []
        errors = []
        for item in data:
            try:
                cleaned.append(super().clean(item, initial))
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)
        if errors:
            raise forms.ValidationError(errors)
        return [item for item in cleaned if item]


class PCBUploadForm(forms.ModelForm):
    receivers = forms.ModelMultipleChoiceField(
        label="Приёмники",
        queryset=Receiver.objects.order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        help_text="Можно выбрать несколько моделей с одинаковым размером платы, например Вега-241 и Вега-341.",
    )
    chips = forms.ModelMultipleChoiceField(
        label="Микросхемы",
        queryset=Chip.objects.select_related("chip_type").order_by("chip_type__sort_order", "chip_type__name", "name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Необязательно. Список и типы пополняет администратор.",
    )
    photos = MultipleImageField(
        label="Фото готового проекта",
        required=False,
        widget=MultiImageInput(attrs={"multiple": True, "accept": "image/jpeg,image/png,image/webp"}),
        help_text="Можно выбрать несколько снимков собранной платы.",
        validators=[FileExtensionValidator(PHOTO_EXTENSIONS)],
    )

    class Meta:
        model = PCBFile
        fields = (
            "title",
            "kind",
            "file",
            "version",
            "receivers",
            "chips",
            "developed_at",
            "source_url",
            "author_name",
            "notes",
            "is_free",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "Комментарий к проекту"}),
            "developed_at": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "source_url": forms.URLInput(attrs={"placeholder": "https://"}),
            "author_name": forms.TextInput(attrs={"placeholder": "Ник или логин на сайте"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["developed_at"].initial = timezone.localdate()
        self.fields["developed_at"].input_formats = ["%Y-%m-%d", "%d.%m.%Y"]
        self.fields["kind"].initial = PCBFile.Kind.MODERN
        self.fields["title"].widget.attrs["placeholder"] = "Например: Вега-241 / 341, плата УНЧ"
        self.fields["source_url"].required = False
        self.fields["author_name"].required = False
        chips = list(self.fields["chips"].queryset)
        groups = []
        current = None
        bucket = []
        for chip in chips:
            label = chip.chip_type.name if chip.chip_type_id else "Без типа"
            if current != label:
                if bucket:
                    groups.append((current, bucket))
                current = label
                bucket = []
            bucket.append((chip.pk, chip.name))
        if bucket:
            groups.append((current, bucket))
        self.fields["chips"].choices = groups
        if not chips:
            self.fields["chips"].help_text = "Пока нет микросхем в справочнике — их добавит администратор."

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and f.name.lower().endswith((".lay", ".lay6")):
            from catalog.lay import LayError, parse

            f.seek(0)
            data = f.read()
            f.seek(0)
            try:
                parsed = parse(data)
            except LayError as exc:
                raise forms.ValidationError(f"Файл не читается как Sprint Layout 5/6: {exc}")
            if not any(b.objects for b in parsed.boards):
                raise forms.ValidationError("В файле Sprint Layout нет ни одного объекта.")
        return f

    def clean_author_name(self):
        return (self.cleaned_data.get("author_name") or "").strip()

    def clean(self):
        cleaned = super().clean()
        nick = cleaned.get("author_name") or ""
        user = get_user_model().objects.filter(username__iexact=nick).first() if nick else None
        self.instance.author = user
        return cleaned


class ReceiverEditForm(forms.ModelForm):
    factories = forms.ModelMultipleChoiceField(
        label="Заводы",
        queryset=Factory.objects.order_by("short_name", "name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    bands = forms.ModelMultipleChoiceField(
        label="Диапазоны",
        queryset=Band.objects.order_by("id"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Receiver
        fields = (
            "name",
            "slug",
            "category",
            "year_start",
            "year_end",
            "produced_count",
            "is_prototype",
            "is_featured",
            "is_hidden",
            "photo",
            "board_drawing",
            "manual",
            "factories",
            "bands",
            "bands_note",
            "description",
            "notes",
            "sensitivity",
            "selectivity",
            "output_power",
            "frequency_response",
            "power_supply",
            "dimensions",
            "weight",
            "transistor_count",
            "receiver_class",
            "original_price",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
