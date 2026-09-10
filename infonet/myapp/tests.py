from datetime import date, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from .models import HouseholdProject, Item, MealPlan, Recipe
from .scheduler import generate_meal_plan, insert_skip_day, set_manual_override


def plans_between(start, days):
    return list(
        MealPlan.objects.filter(
            date__gte=start, date__lt=start + timedelta(days=days)
        ).order_by('date')
    )


class HouseholdProjectTests(TestCase):
    def setUp(self):
        self.url = reverse('household_projects')
        self.data = {
            'name': 'Paint the guest room',
            'description': 'Patch the wall first.\nUse the leftover paint.',
            'project_type': 'app_tech_idea',
            'urgency': '3',
            'scheduled_start': '2026-10-03',
            'estimated_days': '1.5',
        }

    def test_create_persists_every_field_and_refresh_does_not_duplicate(self):
        response = self.client.post(self.url, self.data, follow=True)
        self.assertRedirects(response, self.url)
        project = HouseholdProject.objects.get()
        self.assertEqual(project.name, self.data['name'])
        self.assertEqual(project.description, self.data['description'])
        self.assertEqual(project.project_type, 'app_tech_idea')
        self.assertEqual(project.urgency, 3)
        self.assertEqual(project.scheduled_start, date(2026, 10, 3))
        self.assertEqual(project.estimated_days, Decimal('1.5'))
        self.assertFalse(project.is_completed)
        self.assertContains(response, 'Paint the guest room')
        self.assertContains(response, '1.5 days')
        self.client.get(self.url)
        self.assertEqual(HouseholdProject.objects.count(), 1)

    def test_optional_fields_can_be_blank(self):
        response = self.client.post(self.url, {'name': '  Fix handle  ', 'project_type': 'repair', 'urgency': '2'}, follow=True)
        project = HouseholdProject.objects.get()
        self.assertEqual(project.name, 'Fix handle')
        self.assertEqual(project.description, '')
        self.assertIsNone(project.scheduled_start)
        self.assertIsNone(project.estimated_days)
        self.assertContains(response, 'Not scheduled')
        self.assertContains(response, 'Not estimated')

    def test_bad_input_shows_errors_and_does_not_create(self):
        invalid_fields = [
            ('name', '   '), ('name', 'x' * 201), ('project_type', 'unknown'),
            ('urgency', '5'), ('urgency', 'soon'), ('scheduled_start', '2026-02-30'),
            ('estimated_days', '0'), ('estimated_days', '-1'),
            ('estimated_days', '1.25'), ('estimated_days', '10000'), ('estimated_days', 'lots'),
        ]
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value):
                response = self.client.post(self.url, {**self.data, field: value})
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertEqual(response.context['form']['description'].value(), self.data['description'])
                self.assertFalse(HouseholdProject.objects.exists())

    def test_edit_loads_date_and_updates_existing_record(self):
        self.client.post(self.url, self.data)
        project = HouseholdProject.objects.get()
        url = reverse('project_edit', args=[project.pk])
        response = self.client.get(url)
        self.assertContains(response, 'value="2026-10-03"')
        self.assertContains(response, 'Save changes')
        response = self.client.post(url, {**self.data, 'name': 'Paint both rooms', 'estimated_days': '3'})
        self.assertRedirects(response, self.url)
        project.refresh_from_db()
        self.assertEqual(project.name, 'Paint both rooms')
        self.assertEqual(project.estimated_days, Decimal('3'))
        self.assertEqual(HouseholdProject.objects.count(), 1)

    def test_invalid_edit_preserves_saved_values(self):
        project = HouseholdProject.objects.create(name='Original')
        response = self.client.post(reverse('project_edit', args=[project.pk]), {**self.data, 'estimated_days': '-2'})
        self.assertIn('estimated_days', response.context['form'].errors)
        project.refresh_from_db()
        self.assertEqual(project.name, 'Original')
        self.assertIsNone(project.estimated_days)

    def test_edit_can_clear_schedule_and_estimate(self):
        self.client.post(self.url, self.data)
        project = HouseholdProject.objects.get()
        self.client.post(reverse('project_edit', args=[project.pk]), {
            **self.data, 'scheduled_start': '', 'estimated_days': '',
        })
        project.refresh_from_db()
        self.assertIsNone(project.scheduled_start)
        self.assertIsNone(project.estimated_days)

    def test_completion_is_idempotent_and_can_be_reopened(self):
        project = HouseholdProject.objects.create(name='Repair a hinge')
        url = reverse('project_set_completion', args=[project.pk])
        for _ in range(2):
            self.assertRedirects(self.client.post(url, {'is_completed': 'true'}), self.url)
            project.refresh_from_db()
            self.assertTrue(project.is_completed)
        self.assertNotContains(self.client.get(self.url), 'Repair a hinge')
        self.assertContains(self.client.get(self.url, {'status': 'completed'}), 'Repair a hinge')
        self.client.post(url, {'is_completed': 'false'})
        project.refresh_from_db()
        self.assertFalse(project.is_completed)
        self.assertContains(self.client.get(self.url), 'Repair a hinge')

    def test_invalid_completion_does_not_mutate(self):
        project = HouseholdProject.objects.create(name='Original')
        url = reverse('project_set_completion', args=[project.pk])
        for value in ('', 'maybe', '1'):
            self.assertEqual(self.client.post(url, {'is_completed': value}).status_code, 400)
        project.refresh_from_db()
        self.assertFalse(project.is_completed)

    def test_editing_completed_record_preserves_completion(self):
        project = HouseholdProject.objects.create(name='Finished', is_completed=True)
        url = reverse('project_edit', args=[project.pk])
        response = self.client.post(url, {**self.data, 'is_completed': 'false'})
        self.assertRedirects(response, self.url + '?status=completed')
        project.refresh_from_db()
        self.assertTrue(project.is_completed)
        self.assertEqual(self.client.get(url).context['status'], 'completed')

    def test_ordering_prioritizes_active_urgency_then_schedule(self):
        done = HouseholdProject.objects.create(name='Done', urgency=4, is_completed=True)
        low = HouseholdProject.objects.create(name='Low', urgency=1, scheduled_start=date(2026, 1, 1))
        unscheduled = HouseholdProject.objects.create(name='No date', urgency=3)
        later = HouseholdProject.objects.create(name='Later', urgency=3, scheduled_start=date(2026, 10, 3))
        earlier = HouseholdProject.objects.create(name='Earlier', urgency=3, scheduled_start=date(2026, 10, 1))
        urgent = HouseholdProject.objects.create(name='Urgent', urgency=4)
        response = self.client.get(self.url, {'status': 'all'})
        self.assertEqual(list(response.context['projects']), [urgent, earlier, later, unscheduled, low, done])
        self.assertEqual(response.context['active_count'], 5)
        self.assertEqual(response.context['completed_count'], 1)
        response = self.client.get(self.url, {'status': 'invalid'})
        self.assertEqual(response.context['status'], 'active')
        self.assertNotIn(done, response.context['projects'])

    def test_delete_removes_only_requested_project(self):
        target = HouseholdProject.objects.create(name='Delete me')
        keep = HouseholdProject.objects.create(name='Keep me')
        response = self.client.post(reverse('project_delete', args=[target.pk]))
        self.assertRedirects(response, self.url)
        self.assertEqual(list(HouseholdProject.objects.all()), [keep])

    def test_mutations_reject_get_and_unknown_records(self):
        project = HouseholdProject.objects.create(name='Keep me')
        for route in ('project_set_completion', 'project_delete'):
            self.assertEqual(self.client.get(reverse(route, args=[project.pk])).status_code, 405)
            self.assertEqual(self.client.post(reverse(route, args=[project.pk + 1])).status_code, 404)
        self.assertEqual(self.client.get(reverse('project_edit', args=[project.pk + 1])).status_code, 404)
        self.assertEqual(HouseholdProject.objects.count(), 1)

    def test_csrf_required_for_all_writes(self):
        project = HouseholdProject.objects.create(name='Protected')
        client = Client(enforce_csrf_checks=True)
        urls = [self.url] + [reverse(route, args=[project.pk]) for route in (
            'project_edit', 'project_set_completion', 'project_delete',
        )]
        for url in urls:
            self.assertEqual(client.post(url, self.data).status_code, 403)
        client.get(self.url)
        token = client.cookies['csrftoken'].value
        response = client.post(self.url, {**self.data, 'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 302)

    def test_text_is_escaped_and_page_is_linked(self):
        HouseholdProject.objects.create(name='<script>alert("x")</script>', description='<img src=x onerror=alert(1)>')
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<img src=x')
        self.assertContains(self.client.get(reverse('index')), 'href="/projects/"', count=2)


class SchedulerTests(TestCase):
    def make_recipes(self, specs):
        """specs: list of (name, protein, frequency) tuples."""
        return [
            Recipe.objects.create(name=n, protein_type=p, frequency=f)
            for (n, p, f) in specs
        ]

    def test_full_cycle_before_any_repeat(self):
        recipes = self.make_recipes([
            ('A', 'beef', 1), ('B', 'chicken', 1), ('C', 'fish', 1),
            ('D', 'pork', 1), ('E', 'tofu', 1),
        ])
        start = date(2026, 8, 1)
        generate_meal_plan(start, 15)
        ids = [p.recipe_id for p in plans_between(start, 15)]
        all_ids = {r.id for r in recipes}
        # With no pins, decks align to 5-day chunks; each chunk is one full cycle
        for chunk_start in range(0, 15, 5):
            self.assertEqual(set(ids[chunk_start:chunk_start + 5]), all_ids)

    def test_no_adjacent_repeats_across_cycle_boundaries(self):
        self.make_recipes([('A', 'beef', 1), ('B', 'chicken', 1), ('C', 'fish', 1)])
        start = date(2026, 8, 1)
        generate_meal_plan(start, 30)
        ids = [p.recipe_id for p in plans_between(start, 30)]
        for a, b in zip(ids, ids[1:]):
            self.assertNotEqual(a, b)

    def test_repeat_guard_looks_through_skip_days(self):
        r1, r2 = self.make_recipes([('A', 'beef', 1), ('B', 'chicken', 1)])
        start = date(2026, 8, 3)
        # Friday: recipe A. Saturday: skip. Regenerate from Sunday.
        MealPlan.objects.create(date=start - timedelta(days=2), recipe=r1, plan_type='generated')
        MealPlan.objects.create(date=start - timedelta(days=1), recipe=None, plan_type='skip')
        generate_meal_plan(start, 6)
        # Sunday must not be A again -- Friday and Sunday are consecutive meals
        self.assertEqual(MealPlan.objects.get(date=start).recipe_id, r2.id)

    def test_single_recipe_library_degrades_gracefully(self):
        self.make_recipes([('Only', 'veggie', 1)])
        plans = generate_meal_plan(date(2026, 8, 1), 5)
        self.assertEqual(len(plans), 5)

    def test_no_recipes_returns_empty(self):
        self.assertEqual(generate_meal_plan(date(2026, 8, 1), 5), [])

    def test_regenerate_preserves_manual_and_skip(self):
        r = self.make_recipes([('A', 'beef', 1), ('B', 'chicken', 1), ('C', 'fish', 1)])
        start = date(2026, 8, 1)
        pin_date = start + timedelta(days=3)
        skip_dt = start + timedelta(days=5)
        set_manual_override(pin_date, r[0])
        MealPlan.objects.create(date=skip_dt, recipe=None, plan_type='skip')

        generate_meal_plan(start, 10)

        pinned = MealPlan.objects.get(date=pin_date)
        self.assertEqual(pinned.plan_type, 'manual')
        self.assertEqual(pinned.recipe_id, r[0].id)
        self.assertEqual(MealPlan.objects.get(date=skip_dt).plan_type, 'skip')
        # Day after the pin uses the pinned meal as "yesterday"
        after = MealPlan.objects.get(date=pin_date + timedelta(days=1))
        self.assertNotEqual(after.recipe_id, r[0].id)
        # Everything else got filled
        self.assertEqual(MealPlan.objects.filter(
            date__gte=start, date__lt=start + timedelta(days=10)
        ).count(), 10)

    def test_protein_variety_when_achievable(self):
        self.make_recipes([
            ('C1', 'chicken', 1), ('C2', 'chicken', 1),
            ('B1', 'beef', 1), ('B2', 'beef', 1),
        ])
        start = date(2026, 8, 1)
        generate_meal_plan(start, 20)
        proteins = [p.recipe.protein_type for p in plans_between(start, 20)]
        # A 2/2 split can always alternate protein, so it must
        for a, b in zip(proteins, proteins[1:]):
            self.assertNotEqual(a, b)

    def test_frequency_weighting(self):
        fav, other = self.make_recipes([('Fav', 'beef', 3), ('Other', 'chicken', 1)])
        start = date(2026, 8, 1)
        generate_meal_plan(start, 12)  # 3 cycles of a 4-card deck
        ids = [p.recipe_id for p in plans_between(start, 12)]
        self.assertEqual(ids.count(fav.id), 9)
        self.assertEqual(ids.count(other.id), 3)

    def test_skip_insert_cascades_generated_but_not_pinned(self):
        r = self.make_recipes([('A', 'beef', 1), ('B', 'chicken', 1), ('C', 'fish', 1)])
        d = date(2026, 8, 10)
        # Generated on d, d+1, d+3, d+4; manual pin on d+2
        for offset, rec in zip([0, 1, 3, 4], [r[0], r[1], r[0], r[1]]):
            MealPlan.objects.create(date=d + timedelta(days=offset), recipe=rec, plan_type='generated')
        MealPlan.objects.create(date=d + timedelta(days=2), recipe=r[2], plan_type='manual')

        insert_skip_day(d)

        self.assertEqual(MealPlan.objects.get(date=d).plan_type, 'skip')
        pin = MealPlan.objects.get(date=d + timedelta(days=2))
        self.assertEqual(pin.plan_type, 'manual')
        self.assertEqual(pin.recipe_id, r[2].id)
        # Generated meals hop over the pin: d->d+1, d+1->d+3, d+3->d+4, d+4->d+5
        expected = {
            d + timedelta(days=1): r[0].id,
            d + timedelta(days=3): r[1].id,
            d + timedelta(days=4): r[0].id,
            d + timedelta(days=5): r[1].id,
        }
        for dd, rid in expected.items():
            plan = MealPlan.objects.get(date=dd)
            self.assertEqual(plan.plan_type, 'generated')
            self.assertEqual(plan.recipe_id, rid)

    def test_skip_on_existing_skip_is_noop(self):
        d = date(2026, 8, 10)
        MealPlan.objects.create(date=d, recipe=None, plan_type='skip')
        insert_skip_day(d)
        self.assertEqual(MealPlan.objects.filter(plan_type='skip').count(), 1)


class ViewTests(TestCase):
    def setUp(self):
        self.recipe = Recipe.objects.create(name="Shepherd's Pie", protein_type='beef')

    def test_regenerate_rejects_excessive_num_days(self):
        resp = self.client.post(reverse('meal_regenerate'), {
            'start_date': '2026-08-01', 'num_days': '99999',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_regenerate_survives_garbage_input(self):
        resp = self.client.post(reverse('meal_regenerate'), {
            'start_date': 'not-a-date', 'num_days': 'lots',
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_shopping_delete_requires_post(self):
        item = Item.objects.create(content='eggs')
        resp = self.client.get(reverse('shopping_delete', args=[item.id]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Item.objects.filter(id=item.id).exists())

    def test_recipe_delete_requires_post(self):
        resp = self.client.get(reverse('recipe_delete', args=[self.recipe.id]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Recipe.objects.filter(id=self.recipe.id).exists())

    def test_smart_export_requires_post(self):
        resp = self.client.get(reverse('shopping_smart_export'))
        self.assertEqual(resp.status_code, 405)

    def test_swap_creates_manual_override(self):
        self.client.post(reverse('meal_swap'), {
            'date': '2026-08-01', 'recipe_id': self.recipe.id,
        })
        plan = MealPlan.objects.get(date=date(2026, 8, 1))
        self.assertEqual(plan.plan_type, 'manual')
        self.assertEqual(plan.recipe_id, self.recipe.id)

    def test_calendar_renders_with_awkward_recipe_names(self):
        # Apostrophes in recipe names used to break inline onclick handlers
        set_manual_override(date.today(), self.recipe)
        resp = self.client.get(reverse('meal_calendar'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "openSwapModal('")

    def test_shopping_and_recipe_pages_render(self):
        self.assertEqual(self.client.get(reverse('shopping_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('recipe_list')).status_code, 200)

    def test_calendar_handles_garbage_month(self):
        resp = self.client.get(reverse('meal_calendar'), {'year': '2026', 'month': '13'})
        self.assertEqual(resp.status_code, 400)
