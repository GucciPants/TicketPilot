document.addEventListener('DOMContentLoaded', function() {
    const API_BASE = '/api/v1';

    async function fetchWithButton(button, url, options) {
        button.disabled = true;
        try { return await fetch(url, options); }
        finally { button.disabled = false; }
    }

    // Ticket submission
    document.getElementById('ticketForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = this.querySelector('button');
        const desc = document.getElementById('ticketDesc').value;
        document.getElementById('ticketResult').innerHTML = 'Submitting...';
        try {
            const response = await fetchWithButton(btn, `${API_BASE}/tickets`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({description: desc})
            });
            const data = await response.json();
            document.getElementById('ticketResult').innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            document.getElementById('ticketDesc').value = '';
        } catch (error) {
            document.getElementById('ticketResult').innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });

    // Knowledge base ingestion
    document.getElementById('ingestBtn').addEventListener('click', async function() {
        const btn = this;
        btn.disabled = true;
        const div = document.getElementById('ingestResult');
        div.innerHTML = 'Ingesting...';
        try {
            const response = await fetch(`${API_BASE}/knowledge-base/ingest`, {method: 'POST'});
            div.innerHTML = `<pre>${JSON.stringify(await response.json(), null, 2)}</pre>`;
        } catch (error) {
            div.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        } finally {
            btn.disabled = false;
        }
    });

    // Ticket status check
    document.getElementById('statusForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = this.querySelector('button');
        const ticketId = document.getElementById('ticketId').value;
        const div = document.getElementById('statusResult');
        try {
            const response = await fetchWithButton(btn, `${API_BASE}/tickets/${ticketId}`);
            const data = await response.json();
            div.innerHTML = `
                <div class="ticket-item">
                    <h4>Ticket #${data.id}</h4>
                    <p><strong>Description:</strong> ${data.description}</p>
                    <p><strong>Status:</strong> <span class="ticket-status status-${data.status}">${data.status}</span></p>
                    <p><strong>Resolution:</strong> ${data.resolution || 'Pending...'}</p>
                    <p><small>Created: ${data.created_at}</small></p>
                </div>
            `;
        } catch (error) {
            div.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });

    // Knowledge base search
    document.getElementById('searchForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const btn = this.querySelector('button');
        const query = document.getElementById('searchQuery').value;
        const div = document.getElementById('searchResult');
        try {
            const response = await fetchWithButton(btn, `${API_BASE}/documents/search?query=${encodeURIComponent(query)}&limit=3`);
            const data = await response.json();
            let html = '<h4>Search Results:</h4>';
            if (data.results && data.results.length > 0) {
                data.results.forEach(doc => {
                    html += `<div class="ticket-item">
                        <p><strong>Doc ID:</strong> ${doc.doc_id}</p>
                        <p><strong>Score:</strong> ${(doc.score ?? 0).toFixed(3)}</p>
                        <p><strong>Text:</strong> ${doc.text}</p>
                    </div>`;
                });
            } else {
                html += '<p>No results found.</p>';
            }
            div.innerHTML = html;
        } catch (error) {
            div.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });

    // Load ticket history (via SSE for real-time updates)
    const eventSource = new EventSource(`${API_BASE}/tickets/stream`);
    
    eventSource.addEventListener('tickets_updated', function(e) {
        const data = JSON.parse(e.data);
        const div = document.getElementById('ticketHistory');
        let html = '';
        if (data.tickets && data.tickets.length > 0) {
            data.tickets.forEach(t => {
                const hasResolution = t.status === 'resolved' || t.status === 'escalated';
                html += `<div class="ticket-item">
                    <h4>Ticket #${t.id} - <span class="ticket-status status-${t.status}">${t.status}</span></h4>
                    <p>${t.description}</p>
                    ${hasResolution 
                        ? `<p><strong>Resolution:</strong> ${t.resolution}</p>` 
                        : '<p><em>⏳ Processing...</em></p>'}
                </div>`;
            });
        } else {
            html = '<p>No tickets yet. Create one above!</p>';
        }
        div.innerHTML = html;
    });
    
    eventSource.onerror = function() {
        console.warn('SSE connection error, falling back to polling...');
        // Fallback to polling if SSE fails
        if (!window._pollingFallback) {
            window._pollingFallback = setInterval(async function() {
                try {
                    const response = await fetch(`${API_BASE}/tickets`);
                    const data = await response.json();
                    const div = document.getElementById('ticketHistory');
                    let html = '';
                    if (data.tickets && data.tickets.length > 0) {
                        data.tickets.forEach(t => {
                            const hasResolution = t.status === 'resolved' || t.status === 'escalated';
                            html += `<div class="ticket-item">
                                <h4>Ticket #${t.id} - <span class="ticket-status status-${t.status}">${t.status}</span></h4>
                                <p>${t.description}</p>
                                ${hasResolution 
                                    ? `<p><strong>Resolution:</strong> ${t.resolution}</p>` 
                                    : '<p><em>⏳ Processing...</em></p>'}
                            </div>`;
                        });
                    } else {
                        html = '<p>No tickets yet. Create one above!</p>';
                    }
                    div.innerHTML = html;
                } catch (err) {
                    console.error('Polling fallback error:', err);
                }
            }, 5000);
        }
    };
});
