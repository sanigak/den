// DOC: security#browser



function localDate(dateStr) {
    return new Date(dateStr + 'T00:00:00');
}

// DOC: responsive_layout#calendar
function openSwapModal(cell, trigger) {
    const dateStr = cell.dataset.date;
    const recipeId = cell.dataset.recipeId;
    const editable = cell.dataset.swappable === '1';
    document.getElementById('swapDate').value = dateStr;
    document.getElementById('swapDateDisplay').textContent =
        localDate(dateStr).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });


    const picker = document.getElementById('recipe_id');
    picker.selectedIndex = 0;
    if (recipeId) picker.value = recipeId;
    picker.disabled = !editable;
    document.getElementById('currentMealDisplay').textContent =
        cell.querySelector('.meal-badge')?.textContent.trim() || 'No meal planned.';
    document.getElementById('swapFields').hidden = !editable;
    document.getElementById('pastMealNotice').hidden = editable;
    document.getElementById('skipSelectedDay').hidden = !editable;
    const save = document.getElementById('saveSelectedMeal');
    save.hidden = !editable;
    save.disabled = !editable;
    DenModal.open(document.getElementById('swapModal'), trigger || cell.querySelector('.day-open'));
}

function skipDay(dateStr) {
    const pretty = localDate(dateStr).toLocaleDateString();
    if (confirm('Insert a skip day on ' + pretty + '? Upcoming generated meals shift forward; pinned meals stay put.')) {
        document.getElementById('skipDate').value = dateStr;
        document.getElementById('skipForm').submit();
    }
}


document.querySelectorAll('.calendar-day[data-date]').forEach(function(cell) {
    cell.addEventListener('click', function(e) {
        const btn = e.target.closest('.day-action-btn');
        if (btn && btn.dataset.action === 'skip') {
            skipDay(cell.dataset.date);
            return;
        }
        openSwapModal(cell, e.target.closest('button'));
    });
});

document.getElementById('skipSelectedDay')?.addEventListener('click', function() {
    skipDay(document.getElementById('swapDate').value);
});

document.addEventListener('DOMContentLoaded', function() {
    var today = new Date();
    var nextWeek = new Date(today);
    nextWeek.setDate(today.getDate() + 7);
    const endDate = document.getElementById('shopping_end_date');
    if (endDate) endDate.value = nextWeek.toISOString().split('T')[0];
});
