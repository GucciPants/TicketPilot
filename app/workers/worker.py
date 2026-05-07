"""TicketPilot Worker - Processes tickets using multi-agent orchestration."""
import redis
import json
import os
import time
from app.agents.orchestrator import Orchestrator

# Redis connection
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

# Pipeline orchestrator
orchestrator = Orchestrator()

def main():
    """Main worker loop using multi-agent orchestration."""
    print("TicketPilot Worker started (multi-agent mode). Listening for tickets...")
    
    while True:
        try:
            # Blocking pop from Redis queue
            result = redis_client.brpop("ticket_queue", timeout=5)
            if result:
                _, data = result
                ticket_data = json.loads(data)
                ticket_id = ticket_data.get("ticket_id")
                description = ticket_data.get("description")
                
                print(f"Processing ticket {ticket_id}...")
                
                # Run the full multi-agent pipeline
                resolution = orchestrator.process_ticket(ticket_id, description)
                
                print(f"Ticket {ticket_id} resolved successfully")
                
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
