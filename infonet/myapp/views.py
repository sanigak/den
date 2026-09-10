from datetime import date, timedelta
import calendar

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.db import transaction
from django.db.models import Count
from django.core.paginator import Paginator
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from myapp.models import HouseholdProject, Item, ProjectComment, Recipe, MealPlan
from myapp.forms import HouseholdProjectForm, ItemForm, ProjectCommentForm, RecipeForm
from myapp.device_identity import comment_identity
from myapp.scheduler import generate_meal_plan, insert_skip_day, set_manual_override
from myapp.security import (InputError, acquire_ai, release_ai, ensure_capacity,
                            parse_date, positive_int, valid_range)
from myapp.ai_export import organize


@require_http_methods(['GET', 'HEAD'])
def about(request):
    return render(request, 'about.html')

@require_http_methods(['GET', 'HEAD'])
def services(request):
    return render(request, 'services.html')

@require_http_methods(['GET', 'HEAD'])
def contact(request):
    return render(request, 'contact.html')

@require_http_methods(['GET', 'HEAD'])
def index(request):
    return render(request, 'index.html')


def _txt_download(items, today_str):
    content = '\n'.join(item.content for item in items)
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="shopping_list_{today_str}.txt"'
    return response


# DOC: household_projects#request-flow
@require_http_methods(['GET', 'HEAD', 'POST'])
def household_projects(request, project_id=None):
    project = get_object_or_404(HouseholdProject, pk=project_id) if project_id is not None else None
    form = HouseholdProjectForm(request.POST if request.method == 'POST' else None, instance=project)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            if project is None:
                ensure_capacity(HouseholdProject, 1, 2000)
            saved_project = form.save()
        messages.success(request, 'Project updated.' if project else 'Project added.')
        url = reverse('household_projects')
        if saved_project.is_completed:
            url += '?status=completed'
        return redirect(url)

    status = request.GET.get('status', 'completed' if project and project.is_completed else 'active')
    if status not in ('active', 'completed', 'all'):
        status = 'active'
    projects = HouseholdProject.objects.annotate(comment_count=Count('comments')).order_by(*HouseholdProject._meta.ordering)
    active_count = projects.filter(is_completed=False).count()
    completed_count = projects.filter(is_completed=True).count()
    if status != 'all':
        projects = projects.filter(is_completed=(status == 'completed'))
    return render(request, 'projects/project_list.html', {
        'form': form, 'editing_project': project, 'projects': projects, 'status': status,
        'active_count': active_count, 'completed_count': completed_count,
    })


# DOC: household_projects#comments
@require_http_methods(['GET', 'HEAD'])
def project_detail(request, project_id):
    project = get_object_or_404(HouseholdProject, pk=project_id)
    return _project_thread(request, project, ProjectCommentForm())


def _project_thread(request, project, form, status=200, error=''):
    paginator = Paginator(project.comments.all(), 50)
    page = paginator.get_page(request.GET.get('page', paginator.num_pages))
    return render(request, 'projects/project_detail.html', {
        'project': project, 'comment_form': form, 'comment_page': page,
        'comment_identity': comment_identity(request), 'comment_error': error,
        'display_time_zone': settings.DEN_DISPLAY_TIME_ZONE,
    }, status=status)


@require_POST
def project_add_comment(request, project_id):
    project = get_object_or_404(HouseholdProject, pk=project_id)
    form = ProjectCommentForm(request.POST)
    identity = comment_identity(request)
    if identity is None:
        return _project_thread(request, project, form, 403,
            'Your device could not be identified. Connect Tailscale and try again in a minute.')
    if not form.is_valid():
        return _project_thread(request, project, form, 400)
    with transaction.atomic():
        project = get_object_or_404(HouseholdProject, pk=project_id)
        if project.comments.count() >= 200 or ProjectComment.objects.count() >= 10000:
            return _project_thread(request, project, form, 400, 'The comment limit has been reached.')
        comment = ProjectComment.objects.create(project=project, body=form.cleaned_data['body'],
            author=identity.author, device_id=identity.device_id)
        page = (project.comments.count() + 49) // 50
    messages.success(request, 'Comment added.')
    return redirect(reverse('project_detail', args=[project.pk]) + f'?page={page}#comment-{comment.pk}')


@require_POST
def project_set_completion(request, project_id):
    project = get_object_or_404(HouseholdProject, pk=project_id)
    completed = request.POST.get('is_completed')
    if completed not in ('true', 'false'):
        return HttpResponseBadRequest('is_completed must be true or false.')
    project.is_completed = completed == 'true'
    project.save(update_fields=['is_completed'])
    messages.success(request, 'Project completed.' if project.is_completed else 'Project reopened.')
    return redirect('household_projects')


@require_POST
def project_delete(request, project_id):
    project = get_object_or_404(HouseholdProject, pk=project_id)
    project.delete()
    messages.success(request, 'Project deleted.')
    return redirect('household_projects')


# Shopping List views

@require_http_methods(['GET', 'HEAD', 'POST'])
def shopping_list(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ensure_capacity(Item, 1, 2000)
                form.save()
            return redirect('shopping_list')
    else:
        form = ItemForm()
    items = Item.objects.all()
    return render(request, 'shopping_list.html', {'form': form, 'items': items})


@require_POST
def shopping_delete(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    item.delete()
    return redirect('shopping_list')


@require_http_methods(['GET', 'HEAD'])
def shopping_download(request):
    """Download the shopping list as a .txt file. Read-only, so GET is fine."""
    items = Item.objects.all()
    return _txt_download(items, date.today().strftime('%Y-%m-%d'))


@require_POST
def shopping_clear(request):
    """Clear all items from the shopping list."""
    Item.objects.all().delete()
    return redirect('shopping_list')


@require_POST
def shopping_download_and_clear(request):
    """Return the list as a .txt file and clear it. The client fetches this
    via JS, triggers the download from the blob, then reloads the page --
    which is what fixes the old ghost-list problem."""
    with transaction.atomic():
        items = list(Item.objects.all())
        response = _txt_download(items, date.today().strftime('%Y-%m-%d'))
        Item.objects.filter(pk__in=[item.pk for item in items]).delete()
    return response


@require_POST
def shopping_smart_export(request):
    """DOC: security#ai-export"""
    items = list(Item.objects.all())
    if not items:
        return JsonResponse({'error': 'Shopping list is empty.'}, status=400)

    today_str = date.today().strftime('%Y-%m-%d')
    raw_list = '\n'.join(f"- {item.content}" for item in items)
    if not settings.DEN_AI_ENABLED:
        return _txt_download(items, today_str)
    if len(raw_list.encode('utf-8')) > 32768:
        return HttpResponse('List too large for Smart Export. Use Download instead.', status=413)
    token = acquire_ai()
    try:
        organized_list = organize(raw_list, settings.OPENROUTER_API_KEY)
        if not organized_list:
            raise ValueError('Empty response from API')
    except Exception:
        return _txt_download(items, today_str)
    finally:
        release_ai(token)

    markdown_content = f"# Shopping List - {date.today().strftime('%B %d, %Y')}\n\n{organized_list}"
    response = HttpResponse(markdown_content, content_type='text/markdown')
    response['Content-Disposition'] = f'attachment; filename="shopping_list_{today_str}.md"'
    return response


# Recipe views

@require_http_methods(['GET', 'HEAD'])
def recipe_list(request):
    recipes = Recipe.objects.all().order_by('name')
    return render(request, 'recipes/recipe_list.html', {'recipes': recipes})


@require_http_methods(['GET', 'HEAD', 'POST'])
def recipe_create(request):
    if request.method == 'POST':
        form = RecipeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                ensure_capacity(Recipe, 1, 500)
                form.save()
            return redirect('recipe_list')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_form.html', {'form': form, 'title': 'Add Recipe'})


@require_http_methods(['GET', 'HEAD', 'POST'])
def recipe_edit(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if request.method == 'POST':
        form = RecipeForm(request.POST, instance=recipe)
        if form.is_valid():
            form.save()
            return redirect('recipe_list')
    else:
        form = RecipeForm(instance=recipe)
    return render(request, 'recipes/recipe_form.html', {'form': form, 'title': 'Edit Recipe', 'recipe': recipe})


@require_POST
def recipe_delete(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    recipe.delete()
    return redirect('recipe_list')


# Meal Planner views

@require_http_methods(['GET', 'HEAD'])
def meal_calendar(request):
    """Display the meal planning calendar for a single month."""
    today = date.today()

    try:
        year = positive_int(request.GET.get('year', today.year), 2100)
        month = positive_int(request.GET.get('month', today.month), 12)
        parse_date(f'{year:04d}-{month:02d}-01')
    except (ValueError, TypeError):
        raise InputError('Enter a valid month between 1900 and 2100.') from None

    month_date = date(year, month, 1)
    cal = calendar.Calendar(firstweekday=6)  # Start on Sunday
    month_days = cal.monthdayscalendar(year, month)

    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    meal_plans = {
        mp.date: mp for mp in MealPlan.objects.filter(
            date__gte=month_date,
            date__lte=month_end
        ).select_related('recipe')
    }

    weeks = []
    for week in month_days:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, day)
                meal_plan = meal_plans.get(day_date)
                week_data.append({
                    'day': day,
                    'date': day_date,
                    'is_today': day_date == today,
                    'is_past': day_date < today,
                    'meal_plan': meal_plan,
                })
        weeks.append(week_data)

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    recipes = Recipe.objects.all().order_by('name')

    context = {
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'weeks': weeks,
        'today': today,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'has_previous': (year, month) != (1900, 1),
        'has_next': (year, month) != (2100, 12),
        'recipes': recipes,
        'has_recipes': recipes.exists(),
    }
    return render(request, 'planner/calendar.html', context)


@require_POST
def meal_regenerate(request):
    """Regenerate meal plans from a given date. Preserves manual overrides
    and skip days; only 'generated' plans get replaced."""
    if request.method == 'POST':
        num_days = positive_int(request.POST.get('num_days', 60), 365)
        start_date = parse_date(request.POST.get('start_date', date.today().isoformat()))
        generate_meal_plan(start_date, num_days)

    return redirect('meal_calendar')


@require_POST
def meal_swap(request):
    """Pin a specific recipe to a date (manual override)."""
    if request.method == 'POST':
        meal_date = parse_date(request.POST.get('date'))
        recipe_id = positive_int(request.POST.get('recipe_id'), 9223372036854775807)

        if meal_date and recipe_id:
            recipe = get_object_or_404(Recipe, id=recipe_id)
            set_manual_override(meal_date, recipe)

    return redirect('meal_calendar')


@require_POST
def meal_skip(request):
    """Insert a skip day (eating out, etc.)."""
    if request.method == 'POST':
        skip_date = parse_date(request.POST.get('date'))
        if skip_date:
            insert_skip_day(skip_date)

    return redirect('meal_calendar')


@require_POST
@transaction.atomic
def meal_add_to_shopping(request):
    """Add ingredients from meals in a date range to the shopping list."""
    if request.method == 'POST':
        start_date = parse_date(request.POST.get('start_date'))
        end_date = parse_date(request.POST.get('end_date'))
        valid_range(start_date, (end_date - start_date).days + 1)

        if start_date and end_date:
            meal_plans = MealPlan.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                recipe__isnull=False
            ).select_related('recipe')

            ingredients_to_add = set()
            for mp in meal_plans:
                if mp.recipe and mp.recipe.ingredients:
                    for ingredient in mp.recipe.ingredients:
                        ingredients_to_add.add(f"{ingredient} ({mp.recipe.name})")

            existing_items = set(Item.objects.values_list('content', flat=True))
            additions = sorted(ingredients_to_add - existing_items)
            if any(len(item) > 500 for item in additions):
                raise InputError('An ingredient with its recipe name exceeds 500 characters.')
            ensure_capacity(Item, len(additions), 2000)
            Item.objects.bulk_create([Item(content=item) for item in additions])

    return redirect('shopping_list')
