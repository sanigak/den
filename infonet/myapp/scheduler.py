import random
from datetime import timedelta

from django.db import transaction

from .models import Recipe, MealPlan
from .security import valid_date, valid_range


def _build_deck(recipes):
    """
    Build one shuffled "cycle": every recipe appears `frequency` times.
    The full-cycle invariant (deal the whole deck before anything repeats)
    is enforced simply by exhausting the deck before reshuffling.
    """
    deck = []
    for recipe in recipes:
        deck.extend([recipe] * max(1, recipe.frequency or 1))
    random.shuffle(deck)
    return deck


def _draw(deck, last_recipe=None, avoid_recipe=None):
    """
    Draw a card from the deck, relaxing constraints in order of expendability:

      1. not yesterday's recipe, not tomorrow's pinned recipe,
         AND a different protein than yesterday
      2. drop the protein preference
      3. drop the tomorrow-pin avoidance
      4. take the top card (single-recipe library, or a deck whose only
         remaining cards violate everything -- degrade, don't crash)

    "Not the same recipe as yesterday" is the last constraint standing.
    """
    relaxation_levels = [
        (True, True),    # protein variety + next-day pin both enforced
        (False, True),   # protein preference dropped
        (False, False),  # only identity-vs-yesterday enforced
    ]
    for check_protein, check_next in relaxation_levels:
        for i, cand in enumerate(deck):
            if last_recipe is not None and cand.id == last_recipe.id:
                continue
            if check_next and avoid_recipe is not None and cand.id == avoid_recipe.id:
                continue
            if (check_protein and last_recipe is not None
                    and cand.protein_type == last_recipe.protein_type):
                continue
            return deck.pop(i)
    return deck.pop(0)


def generate_meal_plan(start_date, num_days):
    """
    Fill a date range with generated meals.

    - Deletes only *generated* plans from start_date onward. Manual overrides
      and skip days are preserved and treated as fixed points in the walk.
    - Deals from shuffled full-cycle decks (each recipe appears `frequency`
      times per cycle before anything repeats).
    - Never repeats yesterday's recipe, looking *through* skip days: if
      Saturday is a skip, Friday and Sunday count as consecutive meals.
    - Avoids dealing tomorrow's pinned recipe today (best-effort: yields if
      the deck's final cards force it), and prefers to vary protein.

    Returns the list of created MealPlan objects.
    """
    num_days = valid_range(start_date, num_days)
    recipes = list(Recipe.objects.all())
    if not recipes:
        return []

    with transaction.atomic():
        MealPlan.objects.filter(
            date__gte=start_date, plan_type='generated'
        ).delete()

        pinned = {
            mp.date: mp
            for mp in MealPlan.objects.filter(date__gte=start_date)
        }

        # Last actually-eaten meal before the range, skipping over skip days
        prev = (
            MealPlan.objects
            .filter(date__lt=start_date, recipe__isnull=False)
            .order_by('-date')
            .first()
        )
        last_recipe = prev.recipe if prev else None

        deck = []
        to_create = []
        for offset in range(num_days):
            day = start_date + timedelta(days=offset)

            if day in pinned:
                if pinned[day].recipe is not None:
                    last_recipe = pinned[day].recipe
                # Skip days leave last_recipe untouched on purpose --
                # the repeat guard looks through them.
                continue

            tomorrow = pinned.get(day + timedelta(days=1))
            avoid = tomorrow.recipe if (tomorrow and tomorrow.recipe) else None

            if not deck:
                deck = _build_deck(recipes)

            chosen = _draw(deck, last_recipe=last_recipe, avoid_recipe=avoid)
            to_create.append(
                MealPlan(date=day, recipe=chosen, plan_type='generated')
            )
            last_recipe = chosen

        return MealPlan.objects.bulk_create(to_create)


def insert_skip_day(skip_date):
    """
    Insert a skip day. Generated meals cascade forward to make room, hopping
    over any pinned dates; manual overrides and existing skip days stay put.
    Whatever sits on skip_date itself is displaced regardless of type (the
    user explicitly said "we're not cooking that day").

    Idempotent: inserting a skip on an existing skip day is a no-op.
    """
    valid_date(skip_date)
    with transaction.atomic():
        existing = MealPlan.objects.filter(date=skip_date).first()
        if existing is not None and existing.plan_type == 'skip':
            return
        future = list(
            MealPlan.objects.filter(date__gte=skip_date).order_by('date')
        )
        movable = [
            p for p in future
            if p.plan_type == 'generated' or p.date == skip_date
        ]
        anchored_dates = {
            p.date for p in future
            if p.plan_type != 'generated' and p.date != skip_date
        }

        # Pass 1: assign new dates in calendar order, hopping over anchors.
        # Targets stay monotonic, so no two movable plans collide.
        new_dates = {}
        cursor = None
        for plan in movable:
            target = plan.date + timedelta(days=1)
            if cursor is not None and target <= cursor:
                target = cursor + timedelta(days=1)
            while target in anchored_dates:
                target += timedelta(days=1)
            valid_date(target)
            new_dates[plan.pk] = target
            cursor = target

        # Pass 2: apply latest-first so every save lands on a date the
        # previous save just vacated (unique constraint on date).
        for plan in reversed(movable):
            plan.date = new_dates[plan.pk]
            plan.save(update_fields=['date'])

        MealPlan.objects.create(date=skip_date, recipe=None, plan_type='skip')


def set_manual_override(meal_date, recipe):
    """Pin a specific recipe to a date. Survives regeneration."""
    valid_date(meal_date)
    MealPlan.objects.update_or_create(
        date=meal_date,
        defaults={
            'recipe': recipe,
            'plan_type': 'manual',
        }
    )
