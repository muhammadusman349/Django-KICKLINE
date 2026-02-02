from django import forms
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # Honeypot field for spam (should stay empty)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = [
            'name',
            'email',
            'phone',
            'subject',
            'message',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional phone number'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'How can we help?'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Write your message...'}),
        }

    def clean(self):
        cleaned = super().clean()
        # Simple anti-bot check
        if cleaned.get('website'):
            raise forms.ValidationError('Invalid submission.')
        return cleaned
