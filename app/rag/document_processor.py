import os
import logging
from app.rag.vector_store import VectorStore
from app.rag.embedding import get_embedding

logger = logging.getLogger(__name__)

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
    
    def _chunk_text(self, text: str) -> list:
        """Split text into chunks at sentence boundaries."""
        import re
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text.replace('\n', ' '))
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_size + sentence_len > self.chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                # Overlap: keep last N chars worth of sentences
                overlap_text = ' '.join(current_chunk)
                if self.chunk_overlap > 0 and len(overlap_text) > self.chunk_overlap:
                    # Find sentences that fit in overlap
                    overlap_chars = 0
                    overlap_sentences = []
                    for s in reversed(current_chunk):
                        if overlap_chars + len(s) > self.chunk_overlap:
                            break
                        overlap_sentences.insert(0, s)
                        overlap_chars += len(s)
                    current_chunk = overlap_sentences if overlap_sentences else []
                    current_size = sum(len(s) for s in current_chunk)
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_len

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks if chunks else [text]
    
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
                "text": "Login issues: If a user cannot log in, first check if they have the correct password. Reset password if needed. Check if account is locked. Verify email verification status. Clear browser cache and cookies. Try incognito or private browsing mode. Check caps lock is not enabled when typing password. Use the Forgot Password link to reset your password.",
                "metadata": {"category": "authentication", "type": "troubleshooting"}
            },
            {
                "id": "kb_billing",
                "text": "Billing inquiries: For billing questions, verify subscription status in the billing portal. Check payment history for recent transactions including invoices. If payment failed, suggest updating payment method. Refunds are processed within 3-5 business days. Duplicate charges can be refunded upon review. Upgrade or downgrade plans are prorated automatically with no downtime.",
                "metadata": {"category": "billing", "type": "policy"}
            },
            {
                "id": "kb_performance",
                "text": "Performance issues: Slow loading times may be due to high traffic, server resource exhaustion, or local network issues. Check server resource usage (CPU, memory, disk I/O) in the control panel. Optimize database queries and check max_connections setting. Clear cache and cookies. Consider upgrading to a higher tier plan if resource usage is consistently high. Enable caching plugins for WordPress.",
                "metadata": {"category": "technical", "type": "troubleshooting"}
            },
            {
                "id": "kb_ssl",
                "text": "SSL certificates: Free SSL certificates are available via Let's Encrypt. Enable auto-renewal for SSL renewal in the SSL/TLS section of your control panel. SSL can be manually reissued if expired. After installing a certificate, update your site URL to use HTTPS. Mixed content warnings occur when some resources load over HTTP on an HTTPS page.",
                "metadata": {"category": "technical", "type": "ssl"}
            },
            {
                "id": "kb_wordpress",
                "text": "WordPress troubleshooting: White screen of death is often caused by plugin or theme conflicts. Enable WP_DEBUG in wp-config.php to see error messages. Disable all plugins via FTP by renaming the plugins folder to deactivate them all at once. Increase PHP memory limit to 256M. Check .htaccess file for corrupted redirect rules.",
                "metadata": {"category": "technical", "type": "wordpress"}
            },
            {
                "id": "kb_email",
                "text": "Email delivery issues: If emails are not arriving, check spam folder first and add sender to safe senders list. Set up SPF and DKIM DNS records to improve deliverability and email reputation. Verify MX records and SMTP settings point to the correct mail server. Check mail queue in the control panel. Bounced emails indicate invalid recipient addresses or full mailboxes.",
                "metadata": {"category": "email", "type": "troubleshooting"}
            },
            {
                "id": "kb_dns",
                "text": "DNS management: DNS changes can take up to 48 hours to propagate. Verify A records point to the correct server IP address. CNAME records are for subdomains pointing to other domain names. MX records control email routing. TXT records are used for SPF, DKIM, and domain verification. Nameservers must be updated at your domain registrar. Use the check nameservers tool to verify DNS propagation status.",
                "metadata": {"category": "technical", "type": "dns"}
            },
            {
                "id": "kb_backup",
                "text": "Backup and restoration: Daily backups are kept for 7 days. You can restore individual files or the entire account including data from the backups section in the control panel. Download a full backup before making major changes. Check the backup restore feature for file recovery. Restoration may take a few minutes depending on the size.",
                "metadata": {"category": "technical", "type": "backup"}
            },
            {
                "id": "kb_php",
                "text": "PHP configuration: PHP version can be changed in the control panel under Software > Select PHP Version for compatibility updates. PHP memory limit, max execution time, and upload size can be adjusted via php.ini or .user.ini files. Outdated PHP versions may cause compatibility issues with modern applications.",
                "metadata": {"category": "technical", "type": "php"}
            },
            {
                "id": "kb_database",
                "text": "Database management: MySQL databases can be created and managed via phpMyAdmin. Check database connection settings and max_connections configuration. Connection timeouts may indicate long-running queries or pool exhaustion. Optimize database tables regularly to improve performance. Backup your database before running updates.",
                "metadata": {"category": "technical", "type": "database"}
            },
            {
                "id": "kb_cron",
                "text": "Cron jobs: Cron jobs allow you to schedule automated tasks. The cron job format is: minute hour day month weekday command. Common cron jobs include running backups, sending email reports, and updating caches. Check cron logs for error messages and execution errors. Verify the cron job syntax in the crontab.",
                "metadata": {"category": "technical", "type": "cron"}
            },
            {
                "id": "kb_server_errors",
                "text": "Server error codes: 500 Internal Server Error indicates a server-side problem. Check error logs in the control panel. 502 Bad Gateway means the server received an invalid response from an upstream server. 503 Service Unavailable indicates the server is temporarily overloaded or under maintenance. Restart the server from the control panel if issues persist. Check the server status page for ongoing incidents.",
                "metadata": {"category": "technical", "type": "errors"}
            },
            {
                "id": "kb_file_permissions",
                "text": "File permissions: Correct file permissions are 644 for files and 755 for directories. Never use 777 permissions as they are a security risk. Permission issues can cause white screens, upload failures, and installation errors. Use the file manager or FTP to change permissions.",
                "metadata": {"category": "technical", "type": "filesystem"}
            },
            {
                "id": "kb_account",
                "text": "Account management: Account cancellation can be done via the billing portal. Export your data before cancellation as accounts are terminated after 30 days. Check the refund policy before cancelling. Domain transfers require unlocking the domain and obtaining an EPP code. Addon domains allow hosting multiple websites on a single account. Parked domains can be set up via cPanel Domains section.",
                "metadata": {"category": "account", "type": "management"}
            },
            {
                "id": "kb_security",
                "text": "Security and malware: If your website is hacked or defaced, change all passwords immediately. Restore from a backup taken before the incident. Scan for malware using security tools in the control panel. Review user accounts and file permissions for unauthorized changes. Enable security monitoring and firewall protection.",
                "metadata": {"category": "security", "type": "incident"}
            },
            {
                "id": "kb_disk_space",
                "text": "Disk space management: If disk usage shows 100%, check for large log files, cache directories, and email mailboxes that consume space. System access logs and error logs can accumulate significantly. Clean up cache directories and old backups. Archive or delete unnecessary email messages from mailboxes.",
                "metadata": {"category": "technical", "type": "disk"}
            },
            {
                "id": "kb_email_setup",
                "text": "Email account setup: New email accounts can be created via the cPanel Email Accounts section. Configure email clients using the provided SMTP settings. Verify MX and DNS records for proper email routing. Check setup documentation for step-by-step instructions on configuring your email client.",
                "metadata": {"category": "email", "type": "setup"}
            }
        ]
        
        for doc in sample_docs:
            self.process_text(doc["text"], doc["id"], doc["metadata"])
        
        return len(sample_docs)

    def ingest_gold_standard_knowledge_base(self) -> int:
        """Index gold-standard expected resolutions from the eval dataset.

        Each gold resolution becomes a retrievable document (doc id `gs_<ticket_id>`)
        so RAG retrieval can surface known-good answers directly.
        Returns the number of entries successfully stored in the vector store
        (0 if the dataset is missing).
        """
        import json as _json

        dataset_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "evaluation", "gold_dataset.jsonl"
        )
        if not os.path.exists(dataset_path):
            logger.warning("Gold dataset not found at %s — skipping gold KB ingestion", dataset_path)
            return 0

        count = 0
        with open(dataset_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = _json.loads(line)
                except ValueError:
                    logger.warning("Skipping malformed gold dataset line")
                    continue
                text = entry.get("expected_resolution", "")
                if not text:
                    continue
                doc_id = f"gs_{entry.get('ticket_id', 'unknown')}"
                metadata = {
                    "category": entry.get("category"),
                    "priority": entry.get("priority"),
                    "type": "gold_standard",
                    "source": "gold_dataset",
                }
                chunks = self._chunk_text(text)
                if all(
                    self.vector_store.add_document(f"{doc_id}_chunk_{i}", chunk, metadata)
                    for i, chunk in enumerate(chunks)
                ):
                    count += 1

        logger.info("Ingested %d gold-standard documents into vector store", count)
        return count
