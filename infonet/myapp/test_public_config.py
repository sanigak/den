"""DOC: configuration#verification"""
import io
import json
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .device_identity import comment_identity
from .models import HouseholdProject, Item, ProjectComment, Recipe
from .test_comments import identity_map, person_headers


class PublicConfigurationTests(TestCase):
    def test_configured_owner_names_are_preserved_and_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'devices.json'
            document = identity_map()
            document['devices'][0]['author'] = 'Alexandra <Home> & Family'
            path.write_text(json.dumps(document))
            project = HouseholdProject.objects.create(name='Configured owner')
            with self.settings(DEN_DEVICE_MAP_FILE=str(path)):
                response = self.client.post(f'/projects/{project.pk}/comments/', {'body': 'Update'},
                                            secure=True, **person_headers())
                self.assertEqual(response.status_code, 302)
                self.assertEqual(ProjectComment.objects.get().author, 'Alexandra <Home> & Family')
                page = self.client.get(f'/projects/{project.pk}/', secure=True, **person_headers())
                self.assertContains(page, 'Alexandra &lt;Home&gt; &amp; Family')
                for invalid in ['', ' ', ' Leading', 'Trailing ', 'New\nLine', 'x'*65, 123]:
                    document['devices'][0]['author'] = invalid
                    path.write_text(json.dumps(document))
                    rejected = self.client.post(f'/projects/{project.pk}/comments/', {'body': 'No'},
                                                secure=True, **person_headers())
                    self.assertEqual(rejected.status_code, 403)
                self.assertEqual(ProjectComment.objects.count(), 1)

    def test_display_time_zone_is_configurable(self):
        project = HouseholdProject.objects.create(name='Local clock')
        with self.settings(DEN_DISPLAY_TIME_ZONE='Asia/Seoul'):
            response = self.client.get(f'/projects/{project.pk}/')
            self.assertContains(response, 'Time zone: Asia/Seoul')

    def test_demo_data_requires_empty_development_database(self):
        output = io.StringIO()
        with self.settings(DEN_ENV='production'):
            with self.assertRaises(CommandError):
                call_command('seed_demo', stdout=output)
        self.assertEqual(HouseholdProject.objects.count(), 0)
        call_command('seed_demo', stdout=output)
        counts = (HouseholdProject.objects.count(), Item.objects.count(), Recipe.objects.count())
        self.assertEqual(counts, (3, 3, 2))
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=output)
        self.assertEqual((HouseholdProject.objects.count(), Item.objects.count(), Recipe.objects.count()), counts)

    def test_demo_never_adds_records_to_existing_household(self):
        Item.objects.create(content='Existing household item')
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual(Item.objects.get().content, 'Existing household item')
        self.assertEqual(HouseholdProject.objects.count(), 0)
