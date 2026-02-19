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
    class Meta:
        model = TaskStep
        fields = [
            'order', 'title', 'step_type', 'instruction', 'image',
            'settings', 'publish_time', 'timeout_minutes',
            'reminder_minutes', 'reminder_text', 'requires_moderation',
        ]
        widgets = {
            'order': forms.HiddenInput(),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'step_type': forms.Select(attrs={'class': 'form-select'}),
            'instruction': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'settings': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '{"key": "value"}'}),
            'publish_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'timeout_minutes': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 100px'}),
            'reminder_minutes': forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 100px'}),
            'reminder_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'requires_moderation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_settings(self):
        value = self.cleaned_data.get('settings')
        if not value:
            return {}
        return value


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
