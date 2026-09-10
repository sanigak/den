// DOC: security#browser

document.querySelectorAll('.remove-item-btn').forEach(btn => {
    btn.addEventListener('click', async function() {
        const url = this.dataset.url;
        const itemDiv = this.closest('.shopping-item');

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            if (!response.ok) throw new Error('Remove failed');
            {
                itemDiv.remove();

                const remaining = document.querySelectorAll('.shopping-item').length;
                const countSpan = document.querySelector('.item-count');
                if (countSpan) {
                    countSpan.textContent = remaining + ' item' + (remaining !== 1 ? 's' : '');
                }

                if (remaining === 0) {
                    const cardBody = document.querySelector('.items-card .card-body');
                    const empty = document.createElement('div');
                    empty.className = 'empty-state';
                    const icon = document.createElement('div');
                    icon.className = 'icon';
                    icon.textContent = '📝';
                    const message = document.createElement('p');
                    message.textContent = 'Your shopping list is empty. Add items above to get started!';
                    empty.append(icon, message);
                    cardBody.replaceChildren(empty);
                    document.querySelectorAll('.list-actions, .list-actions-smart').forEach(el => el.remove());
                    if (countSpan) countSpan.remove();
                }
            }
        } catch (error) {
            alert('Could not remove the item. Wait a moment and try again.');
        }
    });
});


const dlClearBtn = document.getElementById('downloadClearBtn');
if (dlClearBtn) {
    dlClearBtn.addEventListener('click', async function() {
        if (!confirm('Download and clear all items?')) return;
        this.disabled = true;
        try {
            await postDownload(this.dataset.url, { reloadAfter: true, fallbackName: 'shopping_list.txt' });
        } catch (err) {
            alert('Download failed. Check the list before retrying.');
            this.disabled = false;
        }
    });
}


const smartBtn = document.getElementById('smartExportBtn');
if (smartBtn) {
    smartBtn.addEventListener('click', async function() {
        const label = this.querySelector('.btn-smart-label');
        const original = label.textContent;
        this.disabled = true;
        label.textContent = 'Organizing your list...';
        try {
            await postDownload(this.dataset.url, { fallbackName: 'shopping_list.md' });
        } catch (err) {
            alert('Smart export failed - try the plain Download button instead.');
        } finally {
            this.disabled = false;
            label.textContent = original;
        }
    });
}
