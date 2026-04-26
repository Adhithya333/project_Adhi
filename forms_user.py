from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class StaffUserCreateForm(UserCreationForm):
    """Staff/Admin creates new user. Restrict user_type via allowed_user_types."""
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    user_type = forms.ChoiceField(choices=User.USER_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'user_type', 'password1', 'password2')

    def __init__(self, *args, allowed_user_types=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_user_types is not None:
            choices = [c for c in User.USER_TYPE_CHOICES if c[0] in allowed_user_types]
            self.fields['user_type'].choices = choices if choices else User.USER_TYPE_CHOICES
        for field in self.fields.values():
            if hasattr(field.widget, 'attrs') and 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'


class StaffUserEditForm(forms.ModelForm):
    """Staff/Admin edits user - no password change. Restrict user_type via allowed_user_types."""
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'user_type', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'user_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_user_types=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_user_types is not None:
            choices = [c for c in User.USER_TYPE_CHOICES if c[0] in allowed_user_types]
            self.fields['user_type'].choices = choices if choices else User.USER_TYPE_CHOICES
