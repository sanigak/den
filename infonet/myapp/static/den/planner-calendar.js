// DOC: security#browser



function localDate(dateStr) {
    return new Date(dateStr + 'T00:00:00');
}

function openSwapModal(dateStr, recipeId) {
    document.getElementById('swapDate').value = dateStr;
    document.getElementById('swapDateDisplay').textContent =
        localDate(dateStr).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });


    if (recipeId) {
        document.getElementById('recipe_id').value = recipeId;
    }
    DenModal.open(document.getElementById('swapModal'));
}

function skipDay(dateStr) {
    const pretty = localDate(dateStr).toLocaleDateString();
    if (confirm('Insert a skip day on ' + pretty + '? Upcoming generated meals shift forward; pinned meals stay put.')) {
        document.getElementById('skipDate').value = dateStr;
        document.getElementById('skipForm').submit();
    }
}


document.querySelectorAll('.calendar-day[data-swappable]').forEach(function(cell) {
    cell.addEventListener('keydown', function(event) {
        if (event.target === cell && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            openSwapModal(cell.dataset.date, cell.dataset.recipeId);
        }
    });
    cell.addEventListener('click', function(e) {
        const btn = e.target.closest('.day-action-btn');
        if (btn && btn.dataset.action === 'skip') {
            skipDay(cell.dataset.date);
            return;
        }
        openSwapModal(cell.dataset.date, cell.dataset.recipeId);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    var today = new Date();
    var nextWeek = new Date(today);
    nextWeek.setDate(today.getDate() + 7);
    document.getElementById('shopping_end_date').value = nextWeek.toISOString().split('T')[0];
});
