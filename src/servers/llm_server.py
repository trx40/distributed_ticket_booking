import grpc
import json
import sys
from concurrent import futures

# Import generated protobuf files
import llm_service_pb2
import llm_service_pb2_grpc


class LLMServer(llm_service_pb2_grpc.LLMServiceServicer):
    """
    LLM Server for domain-specific assistance in movie ticket booking
    Uses a lightweight model optimized for CPU inference
    """
    
    def __init__(self, port=50060):
        self.port = port
        self.generator = None
        print("[LLM Server] Initializing...")
        
        # Try to initialize model
        self._init_model()
        
        # Build domain-specific knowledge base
        self.knowledge_base = self._build_knowledge_base()
        print("[LLM Server] Initialization complete")
    
    def _init_model(self):
        """Initialize the language model"""
        try:
            print("[LLM Server] Loading model (this may take a minute)...")
            from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer
            
            # Using DistilGPT2 for lightweight inference
            model_name = "distilgpt2"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name)
            
            # Set pad token to eos token
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.generator = pipeline(
                'text-generation',
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1  # CPU
            )
            print("[LLM Server] Model loaded successfully")
        except Exception as e:
            print(f"[LLM Server] Warning: Could not load model: {e}")
            print("[LLM Server] Falling back to rule-based responses only")
            self.generator = None
    
    def _build_knowledge_base(self):
        """Build FAQ and knowledge base for ticket booking domain"""
        return {
            "cancel": {
                "keywords": ["cancel", "refund", "return", "cancellation"],
                "response": "To cancel a booking:\n"
                           "1. Go to 'View My Bookings' option\n"
                           "2. Note your booking ID\n"
                           "3. Select 'Cancel Booking' from main menu\n"
                           "4. Enter your booking ID\n"
                           "Refunds are processed within 5-7 business days. "
                           "Cancellations must be made at least 2 hours before the show time."
            },
            "book": {
                "keywords": ["book", "reserve", "buy ticket", "purchase", "how to book"],
                "response": "To book tickets:\n"
                           "1. Select 'View Movies' to see available shows\n"
                           "2. Select 'Book Tickets' from main menu\n"
                           "3. Enter the movie ID\n"
                           "4. Choose your preferred seat numbers (comma-separated)\n"
                           "5. Confirm your booking\n"
                           "6. You'll receive a booking ID for reference\n"
                           "Seats are held for 10 minutes during the booking process."
            },
            "payment": {
                "keywords": ["payment", "pay", "card", "method", "how to pay"],
                "response": "We accept multiple payment methods:\n"
                           "- Credit/Debit cards (Visa, Mastercard, AmEx)\n"
                           "- UPI (Google Pay, PhonePe, Paytm)\n"
                           "- Digital wallets\n"
                           "All payments are processed securely through our gateway. "
                           "You'll receive a confirmation email after successful payment."
            },
            "seats": {
                "keywords": ["seat", "available", "choose", "select seat"],
                "response": "Seat Selection Guide:\n"
                           "- Use 'Get Available Seats' to see which seats are free\n"
                           "- Seats are numbered from 1 to total capacity\n"
                           "- You can book multiple seats at once\n"
                           "- Enter seat numbers separated by commas (e.g., 1,2,3)\n"
                           "- Once booked, seats are immediately reserved for you"
            },
            "price": {
                "keywords": ["price", "cost", "how much", "ticket price"],
                "response": "Ticket Pricing:\n"
                           "- Prices vary by movie and show time\n"
                           "- Premium shows and weekend slots may have higher prices\n"
                           "- Check the movie details for exact pricing\n"
                           "- Total price is calculated based on number of seats\n"
                           "- Prices shown are per ticket"
            },
            "shows": {
                "keywords": ["show time", "timing", "schedule", "when"],
                "response": "Show Times:\n"
                           "- View all available movies and their show times in 'View Movies'\n"
                           "- We have multiple shows throughout the day\n"
                           "- Shows are listed with date and time\n"
                           "- Select a convenient time slot when booking\n"
                           "- Arrive at least 15 minutes before show time"
            },
            "movies": {
                "keywords": ["movie", "film", "what's playing", "available movies"],
                "response": "To see available movies:\n"
                           "- Select option 1 'View Movies' from main menu\n"
                           "- You'll see all currently showing movies\n"
                           "- Information includes: title, show time, price, available seats\n"
                           "- Note the movie ID to book tickets"
            },
            "booking_id": {
                "keywords": ["booking id", "booking number", "reference", "confirmation"],
                "response": "About Booking IDs:\n"
                           "- Each booking gets a unique ID (format: BK000001)\n"
                           "- You receive this ID immediately after successful booking\n"
                           "- Keep this ID safe - you'll need it for:\n"
                           "  * Cancellations\n"
                           "  * Support queries\n"
                           "  * Entry at the theater\n"
                           "- You can view all your booking IDs in 'View My Bookings'"
            },
            "help": {
                "keywords": ["help", "support", "contact", "assistance", "how"],
                "response": "I'm here to help! I can assist with:\n"
                           "- Booking tickets\n"
                           "- Cancellations and refunds\n"
                           "- Payment methods\n"
                           "- Seat selection\n"
                           "- Show timings\n"
                           "- Any other queries about our movie ticket booking system\n"
                           "Just ask your question and I'll do my best to help!"
            },
            "login": {
                "keywords": ["login", "sign in", "account", "password"],
                "response": "Login Information:\n"
                           "- You need to login to book tickets\n"
                           "- Use your username and password\n"
                           "- Your session remains active for 24 hours\n"
                           "- You can logout anytime from the main menu\n"
                           "- Contact support if you forgot your password"
            },
            "problem": {
                "keywords": ["problem", "error", "issue", "not working", "bug"],
                "response": "If you're experiencing issues:\n"
                           "1. Try logging out and logging back in\n"
                           "2. Check your internet connection\n"
                           "3. Make sure you're using valid movie IDs and seat numbers\n"
                           "4. Verify seats are still available\n"
                           "5. Contact support if the problem persists\n"
                           "Please provide your booking ID when contacting support."
            }
        }
    
    def GetLLMAnswer(self, request, context):
        """Process LLM query and return answer"""
        print(f"[LLM Server] Request {request.request_id}: {request.query[:100]}...")
        
        try:
            # Try rule-based response first (faster and more accurate for FAQs)
            answer = self._get_rule_based_answer(request.query)
            
            if answer:
                print(f"[LLM Server] Using rule-based response")
                return llm_service_pb2.LLMAnswerResponse(
                    request_id=request.request_id,
                    answer=answer
                )
            
            # Fall back to LLM if available
            if self.generator:
                print(f"[LLM Server] Using LLM generation")
                answer = self._get_llm_answer(request.query, request.context)
            else:
                print(f"[LLM Server] Using fallback response")
                answer = self._get_fallback_answer(request.query)
            
            return llm_service_pb2.LLMAnswerResponse(
                request_id=request.request_id,
                answer=answer
            )
        
        except Exception as e:
            print(f"[LLM Server] Error: {e}")
            return llm_service_pb2.LLMAnswerResponse(
                request_id=request.request_id,
                answer="I'm sorry, I'm having trouble processing your request. Please try again or contact support."
            )
    
    def _get_rule_based_answer(self, query):
        """Get answer from rule-based knowledge base"""
        query_lower = query.lower()
        
        # Find best matching topic
        best_match = None
        max_matches = 0
        
        for topic, info in self.knowledge_base.items():
            matches = sum(1 for keyword in info["keywords"] if keyword in query_lower)
            if matches > max_matches:
                max_matches = matches
                best_match = info["response"]
        
        return best_match if max_matches > 0 else None
    
    def _get_llm_answer(self, query, context):
        """Generate answer using LLM"""
        try:
            # Build prompt with context
            prompt = f"""You are a helpful customer service assistant for a movie ticket booking system.

Context: {context}

Customer Question: {query}

Provide a helpful, concise answer (2-3 sentences):"""
            
            # Generate response
            response = self.generator(
                prompt,
                max_length=150,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                truncation=True
            )
            
            # Extract answer
            full_text = response[0]['generated_text']
            
            # Try to extract just the answer part
            if "Provide a helpful" in full_text:
                parts = full_text.split("Provide a helpful, concise answer (2-3 sentences):")
                if len(parts) > 1:
                    answer = parts[1].strip()
                else:
                    answer = full_text.replace(prompt, "").strip()
            else:
                answer = full_text.replace(prompt, "").strip()
            
            # Limit response length
            if len(answer) > 500:
                answer = answer[:500] + "..."
            
            # If answer is too short or empty, use fallback
            if len(answer) < 10:
                return self._get_fallback_answer(query)
            
            return answer
            
        except Exception as e:
            print(f"[LLM Server] LLM generation error: {e}")
            return self._get_fallback_answer(query)
    
    def _get_fallback_answer(self, query):
        """Fallback response when LLM is not available or fails"""
        return (
            "Thank you for your question! For assistance with:\n"
            "- Booking tickets: Select 'Book Tickets' from main menu\n"
            "- Cancellations: Use 'Cancel Booking' with your booking ID\n"
            "- Viewing movies: Select 'View Movies'\n"
            "- Your bookings: Select 'View My Bookings'\n\n"
            "For specific help, try asking questions like:\n"
            "- 'How do I book tickets?'\n"
            "- 'How do I cancel my booking?'\n"
            "- 'What payment methods do you accept?'"
        )
    
    def start(self):
        """Start the LLM server"""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        llm_service_pb2_grpc.add_LLMServiceServicer_to_server(self, server)
        server.add_insecure_port(f'[::]:{self.port}')
        server.start()
        
        print(f"[LLM Server] Started on port {self.port}")
        print("[LLM Server] Ready to handle queries")
        print("-" * 60)
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print("\n[LLM Server] Shutting down...")
            server.stop(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Server for Ticket Booking')
    parser.add_argument('--port', type=int, default=50060, help='Server port')
    
    args = parser.parse_args()
    
    server = LLMServer(port=args.port)
    server.start()


if __name__ == '__main__':
    main()