from decimal import Decimal

from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models


class Item(models.Model):
    content = models.TextField(validators=[MaxLengthValidator(500)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.content


# DOC: household_projects#data-contract
class HouseholdProject(models.Model):
    TYPE_CHOICES = [
        ('maintenance', 'Maintenance'),
        ('repair', 'Repair'),
        ('cleaning', 'Cleaning'),
        ('organization', 'Organization'),
        ('app_tech_idea', 'App/Tech Idea'),
        ('ama', 'AMA'),
        ('other', 'Other'),
    ]
    URGENCY_CHOICES = [(1, 'Low'), (2, 'Normal'), (3, 'High'), (4, 'Urgent')]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(10000)])
    project_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    urgency = models.PositiveSmallIntegerField(choices=URGENCY_CHOICES, default=2)
    scheduled_start = models.DateField(null=True, blank=True)
    estimated_days = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.1'))],
    )
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            'is_completed', '-urgency',
            models.F('scheduled_start').asc(nulls_last=True), '-created_at', '-pk',
        ]

    def __str__(self):
        return self.name


# DOC: household_projects#comments
class ProjectComment(models.Model):
    project = models.ForeignKey(HouseholdProject, related_name='comments', on_delete=models.CASCADE)
    body = models.TextField(validators=[MaxLengthValidator(4000)])
    author = models.CharField(max_length=64, editable=False)
    device_id = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [models.CheckConstraint(condition=~models.Q(author=''),
                                              name='project_comment_author_not_empty')]


class Recipe(models.Model):
    PROTEIN_CHOICES = [
        ('beef', 'Beef'),
        ('chicken', 'Chicken'),
        ('pork', 'Pork'),
        ('fish', 'Fish'),
        ('veggie', 'Veggie'),
        ('tofu', 'Tofu'),
    ]

    FREQUENCY_CHOICES = [
        (1, 'Normal'),
        (2, 'Often (2x per rotation)'),
        (3, 'Favorite (3x per rotation)'),
    ]

    name = models.CharField(max_length=200)
    protein_type = models.CharField(max_length=20, choices=PROTEIN_CHOICES)
    ingredients = models.JSONField(default=list)
    frequency = models.PositiveSmallIntegerField(
        choices=FREQUENCY_CHOICES,
        default=1,
        help_text='How many times this recipe appears per rotation cycle.',
    )

    def __str__(self):
        return self.name


class MealPlan(models.Model):
    PLAN_TYPE_CHOICES = [
        ('generated', 'Generated'),
        ('manual', 'Manual Override'),
        ('skip', 'Skip Day'),
    ]

    date = models.DateField(unique=True)
    recipe = models.ForeignKey(Recipe, null=True, blank=True, on_delete=models.SET_NULL)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='generated')

    class Meta:
        ordering = ['date']

    def __str__(self):
        if self.plan_type == 'skip':
            return f"{self.date}: Skip Day"
        return f"{self.date}: {self.recipe.name if self.recipe else 'No recipe'}"


# DOC: security#persistent-state
class SecurityState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    minute = models.BigIntegerField(default=0)
    writes = models.PositiveIntegerField(default=0)
    heavy = models.PositiveIntegerField(default=0)
    ai_day = models.BigIntegerField(default=0)
    ai_attempts = models.PositiveIntegerField(default=0)
    ai_owner = models.CharField(max_length=32, blank=True, default='')
    ai_until = models.FloatField(default=0)
