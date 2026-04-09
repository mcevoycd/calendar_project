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
    nav_layout = forms.ChoiceField(choices=UserPreference.NAV_LAYOUT_CHOICES)
    default_diary_view = forms.ChoiceField(choices=UserPreference.DIARY_VIEW_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('nav_layout', 'default_diary_view'):
            self.fields[field_name].widget.attrs.update({'class': 'form-select'})


class AccountEmailForm(forms.Form):
    email = forms.EmailField(max_length=254)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise forms.ValidationError('Please enter an email address.')

        existing = User.objects.filter(email__iexact=email)
        if self.user is not None:
            existing = existing.exclude(pk=self.user.pk)
        if existing.exists():
            raise forms.ValidationError('That email address is already in use.')

        return email
