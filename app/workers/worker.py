import redis
import json
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Ticket, TicketStatus
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from app.rag.vector_store import VectorStore

# Redis connection
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ticketpilot:ticketpilot@db:5432/ticketpilot")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# LLM setup (using OpenRouter)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
llm = ChatOpenAI(
    model="google/gemini-flash-1.5",  # Default model, can be changed
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    temperature=0.7
)

# Initialize RAG components
vector_store = VectorStore()

def process_ticket(ticket_id: int, description: str) -> str:
    """Process a ticket using LLM with RAG and return resolution."""
    try:
        # Retrieve relevant documents from RAG
        relevant_docs = vector_store.search(description, limit=3)
        
        # Build context from retrieved documents
        context = ""
        if relevant_docs:
            context = "\n\nRelevant knowledge base entries:\n"
            for doc in relevant_docs:
                context += f"- {doc['text'][:200]}...\n"
        
        prompt = f"""You are a support ticket resolution agent. 
        
Ticket description: {description}
{context}

Analyze the ticket and provide a helpful resolution or response. 
If you cannot resolve it, suggest escalation to human support.
Keep the response concise and professional."""

        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Log token usage (for cost tracking)
        if hasattr(response, 'usage_metadata'):
            tokens = response.usage_metadata
            print(f"Ticket {ticket_id} - Tokens used: {tokens}")
        
        return response.content
    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")
        return f"Error: Unable to process ticket - {str(e)}"

def update_ticket_status(ticket_id: int, resolution: str):
    """Update ticket in database with resolution."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            ticket.resolution = resolution
            ticket.status = TicketStatus.RESOLVED
            db.commit()
            print(f"Ticket {ticket_id} updated with resolution")
    except Exception as e:
        print(f"Error updating ticket {ticket_id}: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Main worker loop."""
    print("TicketPilot Worker started. Listening for tickets...")
    
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
                
                # Process ticket
                resolution = process_ticket(ticket_id, description)
                
                # Update database
                update_ticket_status(ticket_id, resolution)
                
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
