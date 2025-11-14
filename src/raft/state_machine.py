import json
import threading
from datetime import datetime

class StateMachine:
    def __init__(self):
        self.lock = threading.Lock()
        self.movies = self._initialize_movies()
        self.bookings = {}
        self.booking_counter = 0
        self.payments = {}
    
    def _initialize_movies(self):
        return {
            "movie1": {
                "title": "The Matrix Reloaded",
                "total_seats": 100,
                "available_seats": list(range(1, 101)),
                "price": 15.0,
                "showtime": "2025-11-20 19:00"
            },
            "movie2": {
                "title": "Inception Dreams",
                "total_seats": 80,
                "available_seats": list(range(1, 81)),
                "price": 12.0,
                "showtime": "2025-11-20 21:00"
            },
            "movie3": {
                "title": "Interstellar Journey",
                "total_seats": 120,
                "available_seats": list(range(1, 121)),
                "price": 18.0,
                "showtime": "2025-11-21 18:00"
            }
        }
    
    def apply_command(self, command_str):
        with self.lock:
            try:
                command = json.loads(command_str)
                operation = command.get('operation')
                
                if operation == 'book_ticket':
                    return self._book_ticket(command)
                elif operation == 'cancel_booking':
                    return self._cancel_booking(command)
                elif operation == 'process_payment':
                    return self._process_payment(command)
                else:
                    return {'status': 'error', 'message': 'Unknown operation'}
            except Exception as e:
                return {'status': 'error', 'message': str(e)}
    
    def _book_ticket(self, command):
        movie_id = command.get('movie_id')
        seats = command.get('seats', [])
        username = command.get('username')
        
        if movie_id not in self.movies:
            return {'status': 'error', 'message': 'Movie not found'}
        
        movie = self.movies[movie_id]
        
        # Check seat availability
        for seat in seats:
            if seat not in movie['available_seats']:
                return {'status': 'error', 'message': f'Seat {seat} not available'}
        
        # Book seats
        for seat in seats:
            movie['available_seats'].remove(seat)
        
        self.booking_counter += 1
        booking_id = f"BK{self.booking_counter:06d}"
        
        self.bookings[booking_id] = {
            'booking_id': booking_id,
            'username': username,
            'movie_id': movie_id,
            'movie_title': movie['title'],
            'seats': seats,
            'price': movie['price'] * len(seats),
            'status': 'confirmed',
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'status': 'success',
            'message': 'Booking confirmed',
            'booking_id': booking_id,
            'details': self.bookings[booking_id]
        }
    
    def _cancel_booking(self, command):
        booking_id = command.get('booking_id')
        username = command.get('username')
        
        if booking_id not in self.bookings:
            return {'status': 'error', 'message': 'Booking not found'}
        
        booking = self.bookings[booking_id]
        
        if booking['username'] != username:
            return {'status': 'error', 'message': 'Unauthorized'}
        
        if booking['status'] == 'cancelled':
            return {'status': 'error', 'message': 'Already cancelled'}
        
        # Release seats
        movie_id = booking['movie_id']
        for seat in booking['seats']:
            self.movies[movie_id]['available_seats'].append(seat)
        self.movies[movie_id]['available_seats'].sort()
        
        booking['status'] = 'cancelled'
        
        return {
            'status': 'success',
            'message': 'Booking cancelled',
            'refund_amount': booking['price']
        }
    
    def _process_payment(self, command):
        booking_id = command.get('booking_id')
        payment_method = command.get('payment_method', 'card')
        
        if booking_id not in self.bookings:
            return {'status': 'error', 'message': 'Booking not found'}
        
        payment_id = f"PAY{len(self.payments) + 1:06d}"
        self.payments[payment_id] = {
            'payment_id': payment_id,
            'booking_id': booking_id,
            'amount': self.bookings[booking_id]['price'],
            'method': payment_method,
            'status': 'completed',
            'timestamp': datetime.now().isoformat()
        }
        
        return {
            'status': 'success',
            'message': 'Payment processed',
            'payment_id': payment_id
        }
    
    def get_state(self):
        with self.lock:
            return {
                'movies': self.movies,
                'bookings': self.bookings,
                'payments': self.payments,
                'booking_counter': self.booking_counter
            }
    
    def set_state(self, state):
        with self.lock:
            self.movies = state.get('movies', self.movies)
            self.bookings = state.get('bookings', self.bookings)
            self.payments = state.get('payments', self.payments)
            self.booking_counter = state.get('booking_counter', self.booking_counter)
    
    def get_available_seats(self, movie_id):
        with self.lock:
            if movie_id in self.movies:
                return self.movies[movie_id]['available_seats']
            return []
    
    def get_user_bookings(self, username):
        with self.lock:
            return [b for b in self.bookings.values() if b['username'] == username]
    
    def get_movies(self):
        with self.lock:
            return [{
                'id': mid,
                'title': m['title'],
                'available_seats': len(m['available_seats']),
                'total_seats': m['total_seats'],
                'price': m['price'],
                'showtime': m['showtime']
            } for mid, m in self.movies.items()]
