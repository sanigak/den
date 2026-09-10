// DOC: household_projects#project-screens
'use strict';
const projectModal = document.getElementById('project-modal');
if (projectModal?.dataset.autoOpen === 'true') {
    DenModal.open(projectModal);
    projectModal.querySelector('[aria-invalid="true"]')?.focus();
}

document.querySelector('.project-table')?.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (event.target.closest('a,button,input,select,textarea') || window.getSelection()?.toString()) return;
    const link = event.target.closest('.project-row')?.querySelector('.project-name-link');
    if (link) window.location.assign(link.href);
});
