document.addEventListener('DOMContentLoaded', function() {
    const API_BASE = '/api/v1';

    // Helper: render markdown safely
    function fmtMarkdown(text) {
        if (!text) return '';
        try {
            return DOMPurify.sanitize(marked.parse(text));
        } catch(e) {
            return esc(text);
        }
    }

    // Helper: escape HTML to prevent XSS
    function esc(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str || ''));
        return div.innerHTML;
    }

    // Helper: fetch with error handling
    async function apiFetch(url, options) {
        var response = await fetch(url, options);
        if (!response.ok) {
            var text = await response.text();
            throw new Error('API Error (' + response.status + '): ' + text.substring(0, 200));
        }
        return response.json();
    }

    // Ticket submission
    document.getElementById('ticketForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        var btn = this.querySelector('button');
        var desc = document.getElementById('ticketDesc').value;
        var resultDiv = document.getElementById('ticketResult');
        resultDiv.innerHTML = 'Submitting...';
        btn.disabled = true;
        try {
            var data = await apiFetch(API_BASE + '/tickets', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({description: desc})
            });
            resultDiv.innerHTML = '<pre>' + esc(JSON.stringify(data, null, 2)) + '</pre>';
            document.getElementById('ticketDesc').value = '';
        } catch (error) {
            resultDiv.innerHTML = '<p style="color:red">Error: ' + esc(error.message) + '</p>';
        } finally {
            btn.disabled = false;
        }
    });

    // Knowledge base ingestion
    document.getElementById('ingestBtn').addEventListener('click', async function() {
        var btn = this;
        var div = document.getElementById('ingestResult');
        div.innerHTML = 'Ingesting...';
        btn.textContent = 'Ingesting...';
        btn.disabled = true;
        try {
            var data = await apiFetch(API_BASE + '/knowledge-base/ingest', {method: 'POST'});
            div.innerHTML = '<pre>' + esc(JSON.stringify(data, null, 2)) + '</pre>';
            btn.textContent = 'Ingest Sample Knowledge Base';
        } catch (error) {
            div.innerHTML = '<p style="color:red">Error: ' + esc(error.message) + '</p>';
            btn.textContent = 'Retry';
        } finally {
            btn.disabled = false;
        }
    });

    // Ticket status check
    document.getElementById('statusForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        var btn = this.querySelector('button');
        var ticketId = document.getElementById('ticketId').value;
        var div = document.getElementById('statusResult');
        btn.disabled = true;
        try {
            var data = await apiFetch(API_BASE + '/tickets/' + ticketId);
            div.innerHTML = '<div class="ticket-item">' +
                '<h4>Ticket #' + esc(data.id) + '</h4>' +
                '<p><strong>Description:</strong> ' + esc(data.description) + '</p>' +
                '<p><strong>Status:</strong> <span class="ticket-status status-' + esc(data.status) + '">' + esc(data.status) + '</span></p>' +
                '<p><strong>Resolution:</strong><br><span class="resolution-content">' + fmtMarkdown(data.resolution || 'Pending...') + '</span></p>' +
                '<p><small>Created: ' + esc(data.created_at) + '</small></p>' +
                '</div>';
        } catch (error) {
            div.innerHTML = '<p style="color:red">Error: ' + esc(error.message) + '</p>';
        } finally {
            btn.disabled = false;
        }
    });

    // Knowledge base search
    document.getElementById('searchForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        var btn = this.querySelector('button');
        var query = document.getElementById('searchQuery').value;
        var div = document.getElementById('searchResult');
        btn.disabled = true;
        try {
            var data = await apiFetch(API_BASE + '/documents/search?query=' + encodeURIComponent(query) + '&limit=3');
            var html = '<h4>Search Results:</h4>';
            if (data.results && data.results.length > 0) {
                data.results.forEach(function(doc) {
                    html += '<div class="ticket-item">' +
                        '<p><strong>Doc ID:</strong> ' + esc(doc.doc_id) + '</p>' +
                        '<p><strong>Score:</strong> ' + (doc.score ?? 0).toFixed(3) + '</p>' +
                        '<p><strong>Text:</strong> ' + esc(doc.text) + '</p></div>';
                });
            } else {
                html += '<p>No results found.</p>';
            }
            div.innerHTML = html;
        } catch (error) {
            div.innerHTML = '<p style="color:red">Error: ' + esc(error.message) + '</p>';
        } finally {
            btn.disabled = false;
        }
    });

    // SSE real-time updates
    var eventSource = null;

    function connectSSE() {
        if (typeof EventSource === 'undefined') {
            startPollingFallback();
            return;
        }
        eventSource = new EventSource(API_BASE + '/tickets/stream');

        eventSource.addEventListener('tickets_updated', function(e) {
            var data = JSON.parse(e.data);
            renderTickets(data.tickets);
        });

        eventSource.onerror = function() {
            console.warn('SSE connection error, falling back to polling...');
            eventSource.close();
            startPollingFallback();
        };
    }

    function startPollingFallback() {
        if (window._pollingFallback) return;
        window._pollingFallback = setInterval(async function() {
            try {
                var response = await fetch(API_BASE + '/tickets');
                var data = await response.json();
                renderTickets(data.tickets);
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 5000);
    }

    function renderTickets(tickets) {
        var div = document.getElementById('ticketHistory');
        var html = '';
        if (tickets && tickets.length > 0) {
            tickets.forEach(function(t) {
                var hasResolution = t.status === 'resolved' || t.status === 'escalated';
                html += '<div class="ticket-item">' +
                    '<h4>Ticket #' + esc(t.id) + ' - <span class="ticket-status status-' + esc(t.status) + '">' + esc(t.status) + '</span></h4>' +
                    '<p>' + esc(t.description) + '</p>' +
                    (hasResolution ? '<p><strong>Resolution:</strong><br><span class="resolution-content">' + fmtMarkdown(t.resolution) + '</span></p>' : '<p><em>⏳ Processing...</em></p>') +
                    '</div>';
            });
        } else {
            html = '<p>No tickets yet. Create one above!</p>';
        }
        div.innerHTML = html;
    }

    connectSSE();
});
