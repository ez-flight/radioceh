from django import forms

from shop.models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ("customer_name", "email", "phone", "comment")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_name"].max_length = 160
        self.fields["comment"].max_length = 2000

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone and sum(ch.isdigit() for ch in phone) < 5:
            raise forms.ValidationError("Похоже, в номере не хватает цифр.")
        return phone
