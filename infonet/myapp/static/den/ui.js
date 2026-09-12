// DOC: security#browser
'use strict';
const DenModal = (() => {
    let active = null;
    let previous = null;
    const focusables = element => [...element.querySelectorAll(
        'a[href],button,input,select,textarea,[tabindex="0"]'
    )].filter(node => !node.disabled && node.getClientRects().length);
    function close() {
        if (!active) return;
        active.classList.remove('show', 'den-modal-open');
        active.setAttribute('aria-hidden', 'true');
        active.removeAttribute('aria-modal');
        document.querySelectorAll('[data-den-inert]').forEach(node => {
            node.inert = false;
            node.removeAttribute('data-den-inert');
        });
        active = null;
        document.body.classList.remove('modal-open');
        if (previous && previous.isConnected) previous.focus();
    }
    function open(element, trigger = document.activeElement) {
        if (!element || !element.classList.contains('modal')) return;
        if (active) close();
        previous = trigger;
        active = element;
        active.classList.add('show', 'den-modal-open');
        active.setAttribute('aria-hidden', 'false');
        active.setAttribute('role', 'dialog');
        active.setAttribute('aria-modal', 'true');
        const title = active.querySelector('.modal-title');
        if (title) {
            title.id = active.id + '-title';
            active.setAttribute('aria-labelledby', title.id);
        }
        let branch = active;
        while (branch.parentElement && branch !== document.body) {
            for (const sibling of branch.parentElement.children) {
                if (sibling !== branch && !sibling.inert) {
                    sibling.inert = true;
                    sibling.setAttribute('data-den-inert', '');
                }
            }
            branch = branch.parentElement;
        }
        document.body.classList.add('modal-open');
        (focusables(active)[0] || active).focus();
    }
    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-toggle]');
        if (trigger) {
            const target = document.getElementById((trigger.dataset.target || '').replace(/^#/, ''));
            if (trigger.dataset.toggle === 'modal') open(target, trigger);
            if (trigger.dataset.toggle === 'collapse' && target) {
                const expanded = target.classList.toggle('show');
                trigger.setAttribute('aria-expanded', String(expanded));
            }
        }
        if (event.target.closest('[data-dismiss="modal"]') || event.target === active) close();
    });
    document.addEventListener('keydown', event => {
        if (!active) return;
        if (event.key === 'Escape') { event.preventDefault(); close(); }
        if (event.key === 'Tab') {
            const nodes = focusables(active);
            const first = nodes[0] || active;
            const last = nodes[nodes.length - 1] || active;
            if (event.shiftKey && (document.activeElement === first || document.activeElement === active)) {
                event.preventDefault(); last.focus();
            } else if (!event.shiftKey && (document.activeElement === last || !nodes.length)) {
                event.preventDefault(); first.focus();
            }
        }
    });
    document.addEventListener('submit', event => {
        const message = event.target.dataset.confirm || event.submitter?.dataset.confirm;
        if (message && !window.confirm(message)) event.preventDefault();
    });
    return {open, close};
})();
