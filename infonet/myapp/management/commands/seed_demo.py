"""DOC: configuration#sample-data"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from myapp.models import HouseholdProject, Item, MealPlan, ProjectComment, Recipe


class Command(BaseCommand):
    help = 'Add synthetic examples to an empty development database.'

    def handle(self, *args, **options):
        if settings.DEN_ENV != 'development':
            raise CommandError('Demo data is available only in development.')
        with transaction.atomic():
            if any(model.objects.exists() for model in (HouseholdProject, Item, MealPlan, ProjectComment, Recipe)):
                raise CommandError('Demo data requires an empty database; existing records are never replaced.')
            HouseholdProject.objects.create(name='Repair the garden gate', project_type='repair', urgency=3,
                description='Tighten the hinges and check the latch.', estimated_days='0.5')
            HouseholdProject.objects.create(name='Organize the pantry', project_type='organization')
            HouseholdProject.objects.create(name='Clean the windows', project_type='cleaning', is_completed=True)
            Item.objects.bulk_create([Item(content='Tomatoes'), Item(content='Rice'), Item(content='Dish soap')])
            Recipe.objects.create(name='Vegetable rice bowl', protein_type='veggie', ingredients=['Rice', 'Carrots'])
            Recipe.objects.create(name='Lemon chicken', protein_type='chicken', ingredients=['Chicken', 'Lemon'])
        self.stdout.write(self.style.SUCCESS('Synthetic demo data added.'))
