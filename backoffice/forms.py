from django import forms
from django.forms import inlineformset_factory

from catalog.models import Product, Task
from steps.models import TaskStep, StepType
from pipeline.models import BuybackResponse


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'wb_article', 'price', 'image', 'description',
            'quantity_total', 'limit_per_user', 'limit_per_user_days', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'wb_article': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quantity_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'limit_per_user': forms.NumberInput(attrs={'class': 'form-control'}),
            'limit_per_user_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['product', 'title', 'payout', 'is_active']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'payout': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaskStepForm(forms.ModelForm):
    # Дополнительные поля вместо сырого JSON settings
    correct_article = forms.CharField(
        label='Правильный артикул',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 12345678'}),
    )
    min_length = forms.IntegerField(
        label='Мин. длина текста',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 120px'}),
    )
    choices_text = forms.CharField(
        label='Варианты выбора',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Один вариант на строку'}),
    )

    class Meta:
        model = TaskStep
        fields = [
            'order', 'title', 'step_type', 'instruction', 'image',
            'publish_time', 'timeout_minutes',
            'reminder_minutes', 'reminder_text', 'requires_moderation',
        ]
        widgets = {
            'order': forms.HiddenInput(),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'step_type': forms.Select(attrs={'class': 'form-select'}),
            'instruction': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'publish_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'timeout_minutes': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 120px'}),
            'reminder_minutes': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 120px'}),
            'reminder_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'requires_moderation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            settings = self.instance.settings or {}
            self.fields['correct_article'].initial = settings.get('correct_article', '')
            self.fields['min_length'].initial = settings.get('min_length')
            choices = settings.get('choices', [])
            self.fields['choices_text'].initial = '\n'.join(choices) if choices else ''

    def save(self, commit=True):
        instance = super().save(commit=False)
        settings = {}
        step_type = self.cleaned_data.get('step_type', '')

        if step_type == StepType.ARTICLE_CHECK:
            val = self.cleaned_data.get('correct_article', '').strip()
            if val:
                settings['correct_article'] = val
        elif step_type == StepType.TEXT_MODERATED:
            val = self.cleaned_data.get('min_length')
            if val:
                settings['min_length'] = val
        elif step_type == StepType.CHOICE:
            text = self.cleaned_data.get('choices_text', '').strip()
            if text:
                settings['choices'] = [line.strip() for line in text.splitlines() if line.strip()]

        instance.settings = settings
        if commit:
            instance.save()
        return instance


TaskStepFormSet = inlineformset_factory(
    Task,
    TaskStep,
    form=TaskStepForm,
    extra=1,
    can_delete=True,
)


class BuybackActionForm(forms.Form):
    """Форма одобрения / отклонения выкупа"""
    ACTION_CHOICES = [
        ('approve', 'Одобрить'),
        ('reject', 'Отклонить'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Причина отклонения...',
        }),
    )


class ModerationForm(forms.Form):
    """Форма модерации ответа на шаг"""
    ACTION_CHOICES = [
        ('approve', 'Одобрить'),
        ('reject', 'Отклонить'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    moderator_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Комментарий модератора...',
        }),
    )
    publish_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    publish_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
    )


class PayoutActionForm(forms.Form):
    """Форма действия с выплатой"""
    ACTION_CHOICES = [
        ('complete', 'Выплачено'),
        ('fail', 'Ошибка'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Заметки...',
        }),
    )
