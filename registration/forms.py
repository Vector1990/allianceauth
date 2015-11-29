from django import forms
from django.contrib.auth.models import User
import re


class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=30, required=True)
    password = forms.CharField(widget=forms.PasswordInput(), required=True)
    password_again = forms.CharField(widget=forms.PasswordInput(), required=True, label="Password Again")
    email = forms.CharField(max_length=254, required=True)
    email_again = forms.CharField(max_length=254, required=True, label="Email Again")

    def clean(self):
        if ' ' in self.cleaned_data['username']:
            raise forms.ValidationError(u'Username cannot contain a space')

        # We attempt to get the user object if we succeed we know email as been used
        try:
            User.objects.get(email=self.cleaned_data['email'])
            raise forms.ValidationError(u'Email as already been used')
        except:
            pass

        if not re.match("^\w+$", self.cleaned_data['username']):
            raise forms.ValidationError(u'Username contains illegal characters')

        if 'password' in self.cleaned_data and 'password_again' in self.cleaned_data:
            if self.cleaned_data['password'] != self.cleaned_data['password_again']:
                raise forms.ValidationError(u'Passwords do not match')

        if 'email' in self.cleaned_data and 'email_again' in self.cleaned_data:
            if self.cleaned_data['email'] != self.cleaned_data['email_again']:
                raise forms.ValidationError(u'Emails do not match')

        return self.cleaned_data
