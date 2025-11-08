from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Income, Expense, Event, Document


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = ['amount', 'date', 'category', 'description']


class ExpenseForm(forms.ModelForm):
    auto_categorize = forms.BooleanField(initial=True, required=False, label='Автокатегоризация')

    class Meta:
        model = Expense
        fields = ['amount', 'date', 'category', 'description']


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['date', 'title', 'description']


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['doc_type', 'params', 'generated_text']


class CustomUserCreationForm(UserCreationForm):
    """
    Форма регистрации с поддержкой анонимной регистрации.
    Email опционален для приватности.
    """
    email = forms.EmailField(required=False, label='Email (опционально)')
    anonymous_mode = forms.BooleanField(
        required=False, 
        initial=False,
        label='Анонимная регистрация (без email)',
        help_text='Создать аккаунт без email для максимальной приватности'
    )
    seed_phrase = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'readonly': True}),
        label='Seed Phrase (сохраните для восстановления)',
        help_text='Сохраните эту фразу в безопасном месте. Она нужна для восстановления доступа.'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Имя пользователя'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email (опционально)'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Подтверждение пароля'})
        self.fields['anonymous_mode'].widget.attrs.update({'class': 'form-check-input'})
    
    def clean(self):
        cleaned_data = super().clean()
        anonymous_mode = cleaned_data.get('anonymous_mode')
        email = cleaned_data.get('email')
        
        # Если анонимный режим, email не обязателен
        if anonymous_mode and not email:
            cleaned_data['email'] = ''
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data.get('email')
        if email:
            user.email = email
        if commit:
            user.save()
            # Создаём профиль пользователя
            from .models import UserProfile
            profile = UserProfile.objects.create(
                user=user,
                encryption_enabled=True,
                local_mode_only=False
            )
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа с поддержкой приватного токена.
    """
    private_token = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Приватный токен (альтернатива паролю)'}),
        label='Приватный токен (опционально)',
        help_text='Используйте приватный токен вместо пароля для входа'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Имя пользователя или Email'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Пароль'})
        self.fields['password'].required = False  # Пароль не обязателен, если есть токен
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        private_token = cleaned_data.get('private_token')
        
        # Если передан приватный токен, проверяем его
        if private_token:
            from .models import UserProfile
            try:
                profile = UserProfile.objects.get(private_token=private_token)
                from django.contrib.auth import authenticate
                user = authenticate(self.request, username=profile.user.username, password=None)
                if user:
                    cleaned_data['user'] = user
                    return cleaned_data
            except UserProfile.DoesNotExist:
                raise forms.ValidationError('Неверный приватный токен')
        
        # Обычная проверка пароля
        if not password:
            raise forms.ValidationError('Введите пароль или приватный токен')
        
        return cleaned_data

