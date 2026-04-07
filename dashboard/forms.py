from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import UserPreference


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('username', 'email', 'password1', 'password2'):
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].widget.attrs.update({'id': 'id_username_signup'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class SettingsForm(forms.Form):
    theme = forms.ChoiceField(choices=UserPreference.THEME_CHOICES)
    nav_layout = forms.ChoiceField(choices=UserPreference.NAV_LAYOUT_CHOICES)
    default_diary_view = forms.ChoiceField(choices=UserPreference.DIARY_VIEW_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('theme', 'nav_layout', 'default_diary_view'):
            self.fields[field_name].widget.attrs.update({'class': 'form-select'})
