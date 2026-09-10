"""DOC: household_projects#author-migration"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('myapp', '0009_projectcomment')]
    operations = [
        migrations.RemoveConstraint(model_name='projectcomment', name='project_comment_household_author'),
        migrations.AlterField(model_name='projectcomment', name='author',
                              field=models.CharField(editable=False, max_length=64)),
        migrations.AddConstraint(model_name='projectcomment', constraint=models.CheckConstraint(
            condition=~models.Q(author=''), name='project_comment_author_not_empty')),
    ]
