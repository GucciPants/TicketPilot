import os
from app.rag.vector_store import VectorStore
from app.rag.embedding import get_embedding

class DocumentProcessor:
    def __init__(self):
        self.vector_store = VectorStore()
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    def process_text(self, text: str, doc_id: str, metadata: dict = None):
        """Process text by chunking and adding to vector store."""
        chunks = self._chunk_text(text)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_metadata = {
                "doc_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {})
            }
            self.vector_store.add_document(chunk_id, chunk, chunk_metadata)
        
        return len(chunks)
    
    def _chunk_text(self, text: str):
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        
        return chunks
    
    def ingest_file(self, file_path: str):
        """Ingest a file (txt, md, etc.)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        doc_id = os.path.basename(file_path)
        return self.process_text(text, doc_id, {"source": file_path})
    
    def ingest_sample_knowledge_base(self):
        """Ingest sample support knowledge base documents."""
        sample_docs = [
            {
                "id": "kb_login_issue",
                "text": "Login issues: If a user cannot log in, first check if they have the correct password. Reset password if needed. Check if account is locked. Verify email verification status. Clear browser cache and cookies. Try incognito or private browsing mode.",
                "metadata": {"category": "authentication", "type": "troubleshooting"}
            },
            {
                "id": "kb_billing",
                "text": "Billing inquiries: For billing questions, verify subscription status in the billing portal. Check payment history for recent transactions. If payment failed, suggest updating payment method. Refunds are processed within 3-5 business days. Duplicate charges can be refunded upon review. Upgrade or downgrade plans are prorated automatically.",
                "metadata": {"category": "billing", "type": "policy"}
            },
            {
                "id": "kb_performance",
                "text": "Performance issues: Slow loading times may be due to high traffic, server resource exhaustion, or local network issues. Check server CPU and memory usage in the control panel. Clear cache and cookies. Optimize images and database queries. Consider upgrading to a higher tier plan if resource usage is consistently high. Enable caching plugins for WordPress.",
                "metadata": {"category": "technical", "type": "troubleshooting"}
            },
            {
                "id": "kb_ssl",
                "text": "SSL certificates: Free SSL certificates are available via Let's Encrypt. Enable auto-renewal in the SSL/TLS section of your control panel. SSL can be manually reissued if expired. After installing SSL, update your site URL to use HTTPS. Mixed content warnings occur when some resources load over HTTP on an HTTPS page.",
                "metadata": {"category": "technical", "type": "ssl"}
            },
            {
                "id": "kb_wordpress",
                "text": "WordPress troubleshooting: White screen of death is often caused by plugin or theme conflicts. Disable all plugins via FTP by renaming the plugins folder to deactivate them all at once. Increase PHP memory limit to 256M in wp-config.php. Enable WP_DEBUG to see error messages. Check .htaccess file for corrupted redirect rules.",
                "metadata": {"category": "technical", "type": "wordpress"}
            },
            {
                "id": "kb_email",
                "text": "Email delivery issues: If emails are not arriving, check spam folder first. Set up SPF and DKIM DNS records to improve deliverability. Verify MX records point to the correct mail server. Check mail queue in the control panel. Email may be delayed due to greylisting. Bounced emails indicate invalid recipient addresses or full mailboxes.",
                "metadata": {"category": "email", "type": "troubleshooting"}
            },
            {
                "id": "kb_dns",
                "text": "DNS management: DNS changes can take up to 48 hours to propagate globally. Verify A records point to the correct server IP address. CNAME records are for subdomains pointing to other domain names. MX records control email routing. TXT records are used for SPF, DKIM, and domain verification. Use the check nameservers tool to verify propagation.",
                "metadata": {"category": "technical", "type": "dns"}
            },
            {
                "id": "kb_backup",
                "text": "Backup and restoration: Daily backups are kept for 7 days. You can restore individual files or the entire account from the backups section in the control panel. Download a full backup before making major changes. Backups include files, databases, and email configurations. Restoration may take a few minutes depending on the size.",
                "metadata": {"category": "technical", "type": "backup"}
            },
            {
                "id": "kb_php",
                "text": "PHP configuration: PHP version can be changed in the control panel under Software > Select PHP Version. PHP memory limit, max execution time, and upload size can be adjusted via php.ini or .user.ini files. Outdated PHP versions may cause compatibility issues with modern applications. Always test PHP version changes on a staging site first.",
                "metadata": {"category": "technical", "type": "php"}
            },
            {
                "id": "kb_database",
                "text": "Database management: MySQL databases can be created and managed via phpMyAdmin. Check database connection settings in your application configuration file. Optimize database tables regularly to improve performance. Backup your database before running updates. Common connection errors include incorrect hostname, username, or password.",
                "metadata": {"category": "technical", "type": "database"}
            },
            {
                "id": "kb_cron",
                "text": "Cron jobs: Cron jobs allow you to schedule automated tasks. The cron job format is: minute hour day month weekday command. Common cron jobs include running backups, sending email reports, and updating caches. Check cron logs for execution errors. Ensure the cron script has proper file permissions.",
                "metadata": {"category": "technical", "type": "cron"}
            },
            {
                "id": "kb_server_errors",
                "text": "Server error codes: 500 Internal Server Error indicates a server-side problem. Check error logs in the control panel. 502 Bad Gateway means the server received an invalid response from an upstream server. 503 Service Unavailable indicates the server is temporarily overloaded or under maintenance. Restart the server from the control panel if issues persist.",
                "metadata": {"category": "technical", "type": "errors"}
            },
            {
                "id": "kb_file_permissions",
                "text": "File permissions: Correct file permissions are 644 for files and 755 for directories. Never use 777 permissions as they are a security risk. Permission issues can cause white screens, upload failures, and installation errors. Use the file manager or FTP to change permissions. Reset file permissions from the control panel if needed.",
                "metadata": {"category": "technical", "type": "filesystem"}
            },
            {
                "id": "kb_account",
                "text": "Account management: Account cancellation can be done via the billing portal. Export your data before cancellation as accounts are terminated after 30 days. Domain transfers require unlocking the domain and obtaining an EPP code. Addon domains allow hosting multiple websites on a single account.",
                "metadata": {"category": "account", "type": "management"}
            }
        ]
        
        for doc in sample_docs:
            self.process_text(doc["text"], doc["id"], doc["metadata"])
        
        return len(sample_docs)
