from django import forms
from .models import HouseholdProject, Item, ProjectComment, Recipe


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['content']
        labels = {
            'content': '',
        }
        widgets = {
            'content': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Add an item...'}),
        }


# DOC: household_projects#validation
class HouseholdProjectForm(forms.ModelForm):
    class Meta:
        model = HouseholdProject
        fields = ['name', 'description', 'project_type', 'urgency', 'scheduled_start', 'estimated_days']
        labels = {
            'name': 'Project name',
            'description': 'Description',
            'project_type': 'Type',
            'urgency': 'Urgency',
            'scheduled_start': 'Scheduled start',
            'estimated_days': 'Estimated days to complete',
        }
        help_texts = {
            'scheduled_start': 'Leave blank if you haven\'t picked a date.',
            'estimated_days': 'Optional. Use 0.5 for a half-day task.',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Paint the guest room'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'What needs doing? (optional)',
            }),
            'project_type': forms.Select(attrs={'class': 'form-control'}),
            'urgency': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_start': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_days': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0.1', 'max': '9999.9', 'step': '0.1', 'placeholder': 'e.g. 2',
            }),
        }


# DOC: household_projects#comments
class ProjectCommentForm(forms.ModelForm):
    class Meta:
        model = ProjectComment
        fields = ['body']
        labels = {'body': 'Add a comment'}
        widgets = {'body': forms.Textarea(attrs={
            'class': 'form-control', 'rows': 4, 'maxlength': 4000, 'aria-describedby': 'comment-help',
            'placeholder': 'Add an update, question, or idea...',
        })}


class RecipeForm(forms.ModelForm):
    ingredients_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter ingredients, one per line',
            'rows': 5
        }),
        label='Ingredients',
        required=False
    )

    class Meta:
        model = Recipe
        fields = ['name', 'protein_type', 'frequency']
        labels = {
            'name': 'Recipe Name',
            'protein_type': 'Protein Type',
            'frequency': 'Rotation Frequency',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter recipe name'}),
            'protein_type': forms.Select(attrs={'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.ingredients:
            self.fields['ingredients_text'].initial = '\n'.join(self.instance.ingredients)

    def save(self, commit=True):
        instance = super().save(commit=False)
        ingredients_text = self.cleaned_data.get('ingredients_text', '')
        instance.ingredients = [line.strip() for line in ingredients_text.split('\n') if line.strip()]
        if commit:
            instance.save()
        return instance

    def clean_ingredients_text(self):
        text = self.cleaned_data['ingredients_text']
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(text.encode('utf-8')) > 32768 or len(lines) > 200 or any(len(line) > 500 for line in lines):
            raise forms.ValidationError('Use at most 200 ingredients, 500 characters each, and 32 KiB total.')
        return '\n'.join(lines)
