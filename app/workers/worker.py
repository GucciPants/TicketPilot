import redis
import json
import os
import time
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Ticket, TicketStatus
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from app.rag.vector_store import VectorStore
from app.metrics import worker_processed_counter, token_usage_counter, ticket_processing_seconds

# Redis connections
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
redis_cache = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"))  # Use DB 1 for cache

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ticketpilot:ticketpilot@db:5432/ticketpilot")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# RAG components
vector_store = VectorStore()

# Model names from environment variables (loaded in process_ticket)
# TRIAGE_MODEL=google/gemini-flash-1.5
# POWER_MODEL=anthropic/claude-sonnet-4

def get_cache_key(query: str) -> str:
    """Generate cache key from query."""
    return f"llm_cache:{hashlib.md5(query.encode()).hexdigest()}"

def get_cached_response(cache_key: str) -> str | None:
    """Get cached LLM response."""
    cached = redis_cache.get(cache_key)
    if cached:
        print(f"Cache hit for key: {cache_key}")
        return cached.decode('utf-8')
    return None

def cache_response(cache_key: str, response: str, ttl: int = 3600):
    """Cache LLM response with TTL."""
    redis_cache.setex(cache_key, ttl, response)

def is_simple_ticket(description: str) -> bool:
    """Determine if ticket is simple enough for cheap model."""
    simple_keywords = ['login', 'password', 'reset', 'billing', 'payment', 'slow', 'error']
    desc_lower = description.lower()
    return any(keyword in desc_lower for keyword in simple_keywords)

def process_ticket(ticket_id: int, description: str) -> str:
    """Process a ticket using LLM with RAG and return resolution."""
    start_time = time.time()
    
    # Load models from environment variables (lazy loading)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return "Error: OPENROUTER_API_KEY not set in .env file."
    
    triage_model_name = os.getenv("TRIAGE_MODEL", "google/gemini-flash-1.5")
    power_model_name = os.getenv("POWER_MODEL", "anthropic/claude-sonnet-4")
    
    try:
        # Check cache first
        cache_key = get_cache_key(description)
        cached = get_cached_response(cache_key)
        if cached:
            print(f"Ticket {ticket_id} - Using cached response")
            return cached
        
        # Retrieve relevant documents from RAG
        relevant_docs = vector_store.search(description, limit=3)
        
        # Build context from retrieved documents
        context = ""
        if relevant_docs:
            context = "\n\nRelevant knowledge base entries:\n"
            for doc in relevant_docs:
                context += f"- {doc['text'][:200]}...\n"
        
        # Choose model based on ticket complexity
        use_cheap_model = is_simple_ticket(description)
        selected_model = triage_model_name if use_cheap_model else power_model_name
        
        # Initialize LLM for this request
        llm = ChatOpenAI(
            model=selected_model,
            openai_api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.3 if use_cheap_model else 0.7
        )
        
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
            input_tokens = tokens.get('input_tokens', 0)
            output_tokens = tokens.get('output_tokens', 0)
            total_tokens = input_tokens + output_tokens
            print(f"Ticket {ticket_id} - Model: {selected_model}, Tokens: {total_tokens}")
            
            # Increment token counter
            token_usage_counter.labels(model=selected_model).inc(total_tokens)
        
        resolution = response.content
        
        # Cache the response
        cache_response(cache_key, resolution)
        
        return resolution
    except Exception as e:
        print(f"Error processing ticket {ticket_id}: {e}")
        return f"Error: Unable to process ticket - {str(e)}"
    finally:
        # Record processing time
        processing_time = time.time() - start_time
        ticket_processing_seconds.observe(processing_time)

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
                
                # Increment worker processed counter
                worker_processed_counter.inc()

        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
