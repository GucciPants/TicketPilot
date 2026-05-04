document.addEventListener('DOMContentLoaded', function() {
    const API_BASE = 'http://localhost:8000/api/v1';
    
    // Ticket submission
    document.getElementById('ticketForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const desc = document.getElementById('ticketDesc').value;
        const resultDiv = document.getElementById('ticketResult');
        
        try {
            const response = await fetch(`${API_BASE}/tickets`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({description: desc})
            });
            const data = await response.json();
            resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            document.getElementById('ticketDesc').value = '';
            loadTicketHistory();
        } catch (error) {
            resultDiv.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });
    
    // Knowledge base ingestion
    document.getElementById('ingestBtn').addEventListener('click', async function() {
        const resultDiv = document.getElementById('ingestResult');
        resultDiv.innerHTML = 'Ingesting...';
        
        try {
            const response = await fetch(`${API_BASE}/knowledge-base/ingest`, {
                method: 'POST'
            });
            const data = await response.json();
            resultDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        } catch (error) {
            resultDiv.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });
    
    // Ticket status check
    document.getElementById('statusForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const ticketId = document.getElementById('ticketId').value;
        const resultDiv = document.getElementById('statusResult');
        
        try {
            const response = await fetch(`${API_BASE}/tickets/${ticketId}`);
            const data = await response.json();
            resultDiv.innerHTML = `
                <div class="ticket-item">
                    <h4>Ticket #${data.id}</h4>
                    <p><strong>Description:</strong> ${data.description}</p>
                    <p><strong>Status:</strong> <span class="ticket-status status-${data.status}">${data.status}</span></p>
                    <p><strong>Resolution:</strong> ${data.resolution || 'Pending...'}</p>
                    <p><small>Created: ${data.created_at}</small></p>
                </div>
            `;
        } catch (error) {
            resultDiv.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });
    
    // Knowledge base search
    document.getElementById('searchForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const query = document.getElementById('searchQuery').value;
        const resultDiv = document.getElementById('searchResult');
        
        try {
            const response = await fetch(`${API_BASE}/documents/search?query=${encodeURIComponent(query)}&limit=3`);
            const data = await response.json();
            let html = '<h4>Search Results:</h4>';
            if (data.results && data.results.length > 0) {
                data.results.forEach(doc => {
                    html += `
                        <div class="ticket-item">
                            <p><strong>Doc ID:</strong> ${doc.doc_id}</p>
                            <p><strong>Score:</strong> ${doc.score.toFixed(3)}</p>
                            <p><strong>Text:</strong> ${doc.text}</p>
                        </div>
                    `;
                });
            } else {
                html += '<p>No results found.</p>';
            }
            resultDiv.innerHTML = html;
        } catch (error) {
            resultDiv.innerHTML = `<p style="color:red">Error: ${error.message}</p>`;
        }
    });
    
    // Load ticket history
    async function loadTicketHistory() {
        const historyDiv = document.getElementById('ticketHistory');
        historyDiv.innerHTML = 'Loading tickets...';
        
        try {
            const response = await fetch(`${API_BASE}/tickets`);
            const data = await response.json();
            let html = '';
            if (data.tickets && data.tickets.length > 0) {
                data.tickets.forEach(ticket => {
                    html += `
                        <div class="ticket-item">
                            <h4>Ticket #${ticket.id} - <span class="ticket-status status-${ticket.status}">${ticket.status}</span></h4>
                            <p>${ticket.description}</p>
                            ${ticket.resolution ? `<p><strong>Resolution:</strong> ${ticket.resolution}</p>` : '<p><em>Processing...</em></p>'}
                        </div>
                    `;
                });
            } else {
                html = '<p>No tickets yet. Create one above!</p>';
            }
            historyDiv.innerHTML = html;
        } catch (error) {
            historyDiv.innerHTML = `<p style="color:red">Error loading tickets: ${error.message}</p>`;
        }
    }
    
    // Load initial ticket history
    loadTicketHistory();
});
