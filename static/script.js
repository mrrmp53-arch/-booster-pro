async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        document.getElementById('fb-followers').textContent =
            data.facebook.followers.toLocaleString();

        document.getElementById('tt-followers').textContent =
            data.tiktok.followers.toLocaleString();

        document.getElementById('status').textContent =
            '● SERVER ONLINE';

    } catch (error) {
        document.getElementById('status').textContent =
            '● CONNECTION ERROR';
    }
}

async function updateStats() {
    const platform = document.getElementById('platform').value;
    const followers = Number(document.getElementById('followers').value);
    const message = document.getElementById('message');

    if (!Number.isSafeInteger(followers) || followers < 0) {
        message.textContent = 'Enter a valid number!';
        return;
    }

    try {
        const response = await fetch('/api/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({platform, followers})
        });

        if (!response.ok) throw new Error('Update failed');

        message.textContent = '✅ Updated successfully!';
        document.getElementById('followers').value = '';
        loadStats();

    } catch (error) {
        message.textContent = '❌ Update failed!';
    }
}

loadStats();
async function updateAnalytics() {
    const platform = document.getElementById('analytics-platform').value;

    const views = Number(document.getElementById('views').value);
    const likes = Number(document.getElementById('likes').value);
    const comments = Number(document.getElementById('comments').value);

    const message = document.getElementById('analytics-message');

    const values = [views, likes, comments];

    if (values.some(v => !Number.isSafeInteger(v) || v < 0)) {
        message.textContent = 'Enter valid numbers!';
        return;
    }

    try {
        const response = await fetch('/api/analytics/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({
                platform,
                views,
                likes,
                comments
            })
        });

        if (!response.ok) throw new Error('Update failed');

        message.textContent = '✅ Analytics Saved!';

    } catch (error) {
        message.textContent = '❌ Save Failed!';
    }
}
async function loadAnalytics() {
    try {
        const response = await fetch('/api/analytics');
        const data = await response.json();

        console.log('Facebook Analytics:', data.facebook);
        console.log('TikTok Analytics:', data.tiktok);

    } catch (error) {
        console.log('Analytics loading failed');
    }
}

loadAnalytics();
setInterval(loadAnalytics, 10000);
async function loadAnalytics() {
    try {
        const response = await fetch('/api/analytics');
        if (!response.ok) throw new Error('Loading failed');

        const data = await response.json();

        document.getElementById('fb-views').textContent =
            data.facebook.views.toLocaleString();

        document.getElementById('fb-likes').textContent =
            data.facebook.likes.toLocaleString();

        document.getElementById('fb-comments').textContent =
            data.facebook.comments.toLocaleString();

        document.getElementById('tt-views').textContent =
            data.tiktok.views.toLocaleString();

        document.getElementById('tt-likes').textContent =
            data.tiktok.likes.toLocaleString();

        document.getElementById('tt-comments').textContent =
            data.tiktok.comments.toLocaleString();

    } catch (error) {
        console.log('Analytics loading failed');
    }
}

loadAnalytics();
setInterval(loadAnalytics, 10000);
async function saveLinks() {
    const facebook = document.getElementById('facebook-url').value.trim();
    const tiktok = document.getElementById('tiktok-url').value.trim();
    const message = document.getElementById('links-message');

    if (facebook && !facebook.startsWith('https://')) {
        message.textContent = 'Facebook URL must use HTTPS';
        return;
    }

    if (tiktok && !tiktok.startsWith('https://')) {
        message.textContent = 'TikTok URL must use HTTPS';
        return;
    }

    try {
        const response = await fetch('/api/links', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
            },
            body: JSON.stringify({facebook, tiktok})
        });

        if (!response.ok) throw new Error('Save failed');

        message.textContent = '✅ Profile Links Saved!';
    } catch (error) {
        message.textContent = '❌ Save Failed!';
    }
}

async function loadLinks() {
    try {
        const response = await fetch('/api/links');
        if (!response.ok) throw new Error('Load failed');

        const data = await response.json();

        document.getElementById('facebook-url').value = data.facebook || '';
        document.getElementById('tiktok-url').value = data.tiktok || '';
    } catch (error) {
        console.log('Links loading failed');
    }
}

loadLinks();
async function loadProfilePreview() {
    try {
        const response = await fetch('/api/links');
        if (!response.ok) throw new Error('Load failed');

        const data = await response.json();

        const fb = document.getElementById('facebook-preview');
        const tt = document.getElementById('tiktok-preview');
        const msg = document.getElementById('preview-message');

        if (data.facebook) {
            fb.href = data.facebook;
            fb.hidden = false;
        }

        if (data.tiktok) {
            tt.href = data.tiktok;
            tt.hidden = false;
        }

        if (data.facebook || data.tiktok) {
            msg.textContent = '✅ Profiles Ready!';
        }
    } catch (error) {
        console.log('Profile preview loading failed');
    }
}

loadProfilePreview();
