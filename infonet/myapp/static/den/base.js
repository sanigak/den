// DOC: security#browser

function getCookie(name) {
    const value = '; ' + document.cookie;
    const parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

async function postDownload(url, options) {
    const opts = options || {};
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    });
    if (!resp.ok) {
        throw new Error('Request failed (' + resp.status + ')');
    }
    const blob = await resp.blob();
    const dispo = resp.headers.get('Content-Disposition') || '';
    const match = dispo.match(/filename="?([^";]+)"?/);
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = match ? match[1] : (opts.fallbackName || 'download.txt');
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    if (opts.reloadAfter) {
        location.reload();
    }
}
