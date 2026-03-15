from django import forms


class StudyForm(forms.Form):
    first_name = forms.CharField(
        max_length=100, required=True, help_text="Введіть ім'я"
    )
    last_name = forms.CharField(max_length=100, required=False)
