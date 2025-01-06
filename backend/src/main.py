from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Set, Tuple
import json
import random
import asyncio
from datetime import datetime, timedelta
import os

app = FastAPI()

# Get frontend URL from environment variable or use a default for local development
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporarily allow all origins for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def handle_head_requests(request: Request, call_next):
    response = await call_next(request)
    if request.method == "HEAD":
        return JSONResponse(content={}, status_code=200)
    return response

@app.get("/")
@app.head("/")
async def read_root():
    return {"status": "healthy", "message": "Whist Game Backend API"}

@app.get("/health")
@app.head("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/debug")
async def debug_info():
    return {
        "frontend_url": FRONTEND_URL,
        "environment": os.environ.get("ENVIRONMENT"),
        "allowed_origins": [FRONTEND_URL],
        "python_version": os.environ.get("PYTHON_VERSION"),
        "server_time": datetime.now().isoformat()
    }

# Store active connections and games
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.games: Dict[str, 'Game'] = {}
        self.player_to_game: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, player_id: str):
        await websocket.accept()
        self.active_connections[player_id] = websocket

    def disconnect(self, player_id: str):
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        if player_id in self.player_to_game:
            game_id = self.player_to_game[player_id]
            if game_id in self.games:
                self.games[game_id].remove_player(player_id)
            del self.player_to_game[player_id]

    async def broadcast_to_game(self, game_id: str, message: dict):
        if game_id in self.games:
            game = self.games[game_id]
            for player_id in game.player_order:
                if player_id in self.active_connections:
                    await self.active_connections[player_id].send_json(message)

class Card:
    def __init__(self, suit: str, value: str):
        self.suit = suit
        self.value = value

    def to_dict(self):
        return {"suit": self.suit, "value": self.value}

    @property
    def power(self):
        values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        return values.index(self.value)

class Deck:
    def __init__(self):
        self.reset()

    def reset(self):
        suits = ["hearts", "diamonds", "clubs", "spades"]
        values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.cards = [Card(suit, value) for suit in suits for value in values]
        random.shuffle(self.cards)

    def draw(self) -> Optional[Card]:
        return self.cards.pop() if self.cards else None

class AIPlayer:
    def __init__(self, player_id: str, difficulty: str = 'normal'):
        self.player_id = player_id
        self.difficulty = difficulty
    
    def calculate_bid(self, cards: List[Card], trump_card: Optional[Card], game_stage: str) -> int:
        if game_stage == "no_trump":
            return self._calculate_no_trump_bid(cards)
        return self._calculate_trump_bid(cards, trump_card.suit if trump_card else None)
    
    def _calculate_trump_bid(self, cards: List[Card], trump_suit: Optional[str]) -> int:
        score = 0
        for card in cards:
            # High cards in trump suit are worth more
            if card.suit == trump_suit:
                if card.value in ['A', 'K', 'Q', 'J']:
                    score += 1.0
                else:
                    score += 0.5
            # High cards in other suits
            elif card.value in ['A', 'K']:
                score += 0.8
            elif card.value in ['Q', 'J']:
                score += 0.4
        return max(0, round(score))
    
    def _calculate_no_trump_bid(self, cards: List[Card]) -> int:
        score = 0
        for card in cards:
            if card.value == 'A':
                score += 1.0
            elif card.value == 'K':
                score += 0.8
            elif card.value == 'Q':
                score += 0.5
            elif card.value == 'J':
                score += 0.3
        return max(0, round(score))
    
    def choose_card(self, cards: List[Card], current_round: Dict[str, Card], 
                   trump_suit: Optional[str], led_suit: Optional[str], 
                   game_stage: str) -> int:
        playable_cards = self._get_playable_cards(cards, led_suit)
        if not playable_cards:
            return 0  # Should never happen as we always have at least one card
        
        if not current_round:  # We're leading
            return self._choose_lead_card(cards, trump_suit, game_stage)
        
        return self._choose_follow_card(cards, current_round, trump_suit, led_suit, game_stage)
    
    def _get_playable_cards(self, cards: List[Card], led_suit: Optional[str]) -> List[Tuple[int, Card]]:
        if not led_suit:
            return [(i, card) for i, card in enumerate(cards)]
        
        # Must follow suit if possible
        same_suit_cards = [(i, card) for i, card in enumerate(cards) if card.suit == led_suit]
        return same_suit_cards if same_suit_cards else [(i, card) for i, card in enumerate(cards)]
    
    def _choose_lead_card(self, cards: List[Card], trump_suit: Optional[str], game_stage: str) -> int:
        # Strategy: Lead with high cards in non-trump suits
        non_trump_high_cards = [(i, card) for i, card in enumerate(cards) 
                              if card.suit != trump_suit and card.value in ['A', 'K']]
        if non_trump_high_cards:
            return non_trump_high_cards[0][0]
        
        # If no high cards, lead lowest card
        return min(range(len(cards)), 
                  key=lambda i: (cards[i].suit == trump_suit, 
                               self._card_value(cards[i])))
    
    def _choose_follow_card(self, cards: List[Card], current_round: Dict[str, Card],
                          trump_suit: Optional[str], led_suit: str, game_stage: str) -> int:
        playable = self._get_playable_cards(cards, led_suit)
        if not playable:
            return 0
        
        # Get highest card played so far
        highest_played = max(current_round.values(), 
                           key=lambda c: (c.suit == trump_suit, self._card_value(c)))
        
        # If we can't follow suit, try to trump if valuable
        if led_suit and all(card.suit != led_suit for _, card in playable):
            trump_cards = [(i, card) for i, card in playable if card.suit == trump_suit]
            if trump_cards:
                return trump_cards[0][0]  # Play lowest trump
            return playable[0][0]  # Discard lowest card
        
        # Try to win the trick if possible
        can_win = [(i, card) for i, card in playable 
                   if (card.suit == trump_suit and highest_played.suit != trump_suit) or
                      (card.suit == highest_played.suit and 
                       self._card_value(card) > self._card_value(highest_played))]
        
        if can_win:
            return min(can_win, key=lambda x: self._card_value(x[1]))[0]  # Win with lowest possible
        
        return min(playable, key=lambda x: self._card_value(x[1]))[0]  # Play lowest card
    
    def _card_value(self, card: Card) -> int:
        values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, 
                 '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return values[card.value]

class Game:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.player_order: List[str] = []  # List to maintain player order
        self.players: Dict[str, List[Card]] = {}  # Map player_id to their cards
        self.deck = Deck()
        self.current_player: Optional[str] = None
        self.started = False
        self.min_players = 3
        self.max_players = 5
        self.trump_card: Optional[Card] = None
        self.current_round: Dict[str, Card] = {}
        self.bids: Dict[str, int] = {}
        self.tricks_won: Dict[str, int] = {}
        self.scores: Dict[str, int] = {}
        self.round_number = 1
        self.cards_per_round = 1
        self.phase = "waiting"  # waiting, bidding, playing, round_over, game_over
        self.led_suit: Optional[str] = None
        self.dealer_index = 0
        self.game_stage = "ascending"  # ascending, no_trump, descending
        self.no_trump_rounds_played = 0
        self.player_names: Dict[str, str] = {}  # Map player_id to display_name
        self.created_at = datetime.now()
        self.ai_players: Dict[str, AIPlayer] = {}
    
    def add_player(self, player_id: str) -> bool:
        if len(self.player_order) >= self.max_players or self.started:
            return False
        if player_id not in self.player_order:
            self.player_order.append(player_id)
            self.players[player_id] = []
            self.scores[player_id] = 0
            self.tricks_won[player_id] = 0
        return True
    
    def add_ai_player(self) -> str:
        ai_id = f"ai_player_{len(self.ai_players) + 1}"
        self.ai_players[ai_id] = AIPlayer(ai_id)
        self.add_player(ai_id)  # Use existing add_player method
        self.player_names[ai_id] = f"Computer {len(self.ai_players)}"
        return ai_id
    
    def start_game(self) -> bool:
        if len(self.player_order) < self.min_players or self.started:
            return False
        
        self.started = True
        self._start_new_round()
        return True
    
    def _start_new_round(self):
        self.deck.reset()
        self.current_round = {}
        self.bids = {}
        self.tricks_won = {p: 0 for p in self.player_order}
        self.phase = "bidding"
        
        # Deal cards
        for player_id in self.player_order:
            self.players[player_id] = []
            for _ in range(self.cards_per_round):
                card = self.deck.draw()
                if card:
                    self.players[player_id].append(card)
        
        # Set trump card if not in no_trump stage
        if self.game_stage != "no_trump":
            self.trump_card = self.deck.draw()
        else:
            self.trump_card = None
        
        # Set first player (after dealer)
        self.dealer_index = (self.dealer_index + 1) % len(self.player_order)
        self.current_player = self.player_order[(self.dealer_index + 1) % len(self.player_order)]
        
    def remove_player(self, player_id: str):
        if player_id in self.player_order:
            self.player_order.remove(player_id)
            self.players.pop(player_id, None)
            self.scores.pop(player_id, None)
            self.tricks_won.pop(player_id, None)
            self.bids.pop(player_id, None)
            self.current_round.pop(player_id, None)
            self.player_names.pop(player_id, None)
            if player_id in self.ai_players:
                self.ai_players.pop(player_id, None)
    
    def get_game_state(self, player_id: str) -> dict:
        return {
            "game_id": self.game_id,
            "players": self.player_order,
            "current_player": self.current_player,
            "started": self.started,
            "trump_card": self.trump_card.to_dict() if self.trump_card else None,
            "current_round": {p: card.to_dict() for p, card in self.current_round.items()},
            "bids": self.bids,
            "tricks_won": self.tricks_won,
            "scores": self.scores,
            "round_number": self.round_number,
            "cards_per_round": self.cards_per_round,
            "phase": self.phase,
            "game_stage": self.game_stage,
            "player_names": self.player_names,
            "your_cards": [card.to_dict() for card in self.players.get(player_id, [])],
            "created_at": self.created_at.isoformat()
        }

    def make_bid(self, player_id: str, bid: int) -> bool:
        if not self.started or self.phase != "bidding" or player_id != self.current_player:
            return False
        
        if bid < 0 or bid > self.cards_per_round:
            return False
        
        self.bids[player_id] = bid
        
        # Move to next player for bidding
        current_index = self.player_order.index(self.current_player)
        next_index = (current_index + 1) % len(self.player_order)
        self.current_player = self.player_order[next_index]
        
        # If all players have bid, start playing phase
        if len(self.bids) == len(self.players):
            self.phase = "playing"
            # First player after dealer leads
            self.current_player = self.player_order[(self.dealer_index + 1) % len(self.player_order)]
        
        return True

    def play_card(self, player_id: str, card_index: int) -> bool:
        if not self.started or self.phase != "playing" or player_id != self.current_player:
            return False

        if card_index >= len(self.players[player_id]):
            return False

        player_cards = self.players[player_id]
        card_to_play = player_cards[card_index]

        # If this is the first card of the trick
        if not self.current_round:
            self.led_suit = card_to_play.suit
        else:
            # Check if player is following suit when required
            if self.led_suit:
                has_led_suit = any(card.suit == self.led_suit for card in player_cards)
                if has_led_suit and card_to_play.suit != self.led_suit:
                    return False  # Must follow suit if possible

        # Play the card
        self.players[player_id].pop(card_index)
        self.current_round[player_id] = card_to_play

        # If all players played, evaluate the trick
        if len(self.current_round) == len(self.players):
            trick_winner = self._evaluate_trick()
            self.tricks_won[trick_winner] += 1
            self.current_round.clear()
            self.led_suit = None
            self.current_player = trick_winner  # Winner leads next trick
            
            # If round is over (no cards left), score the round and start new round
            if all(len(cards) == 0 for cards in self.players.values()):
                self._score_round()
                self.cards_per_round += 1
                self.round_number += 1
                self._start_new_round()
        else:
            # Move to next player
            current_index = self.player_order.index(self.current_player)
            self.current_player = self.player_order[(current_index + 1) % len(self.player_order)]
        
        return True

    def _evaluate_trick(self) -> str:
        winning_player = None
        winning_card = None
        
        for player_id, card in self.current_round.items():
            if winning_card is None:
                winning_player = player_id
                winning_card = card
                continue
            
            # If we're in no_trump stage or both cards are not trump
            if self.game_stage == "no_trump" or (
                self.trump_card and 
                card.suit != self.trump_card.suit and 
                winning_card.suit != self.trump_card.suit
            ):
                # If this card is led suit and winning card is not
                if card.suit == self.led_suit and winning_card.suit != self.led_suit:
                    winning_player = player_id
                    winning_card = card
                # If both cards are same suit, compare values
                elif card.suit == winning_card.suit and card.power > winning_card.power:
                    winning_player = player_id
                    winning_card = card
            # If not no_trump stage, handle trump cards
            else:
                # If this card is trump and winning card is not
                if card.suit == self.trump_card.suit and winning_card.suit != self.trump_card.suit:
                    winning_player = player_id
                    winning_card = card
                # If both cards are trump
                elif card.suit == self.trump_card.suit and winning_card.suit == self.trump_card.suit:
                    if card.power > winning_card.power:
                        winning_player = player_id
                        winning_card = card
                # If neither card is trump and this card is led suit
                elif card.suit == self.led_suit and winning_card.suit != self.led_suit:
                    winning_player = player_id
                    winning_card = card
                
        return winning_player

    def _score_round(self):
        for player_id in self.players:
            tricks_won = self.tricks_won[player_id]
            bid = self.bids[player_id]
            
            if tricks_won == bid:
                # Correct bid: 10 points + 2 points per trick
                self.scores[player_id] += 10 + (tricks_won * 2)
            else:
                # Wrong bid: only 2 points per trick
                self.scores[player_id] += tricks_won * 2

    async def handle_ai_turns(self):
        while True:
            await asyncio.sleep(1)  # Check every second
            
            if not self.started or not self.current_player in self.ai_players:
                continue
            
            ai = self.ai_players[self.current_player]
            
            if self.phase == 'bidding':
                bid = ai.calculate_bid(
                    self.players[self.current_player],
                    self.trump_card,
                    self.game_stage
                )
                self.make_bid(self.current_player, bid)
            
            elif self.phase == 'playing':
                card_index = ai.choose_card(
                    self.players[self.current_player],
                    self.current_round,
                    self.trump_card.suit if self.trump_card else None,
                    self.led_suit,
                    self.game_stage
                )
                self.play_card(self.current_player, card_index)

manager = ConnectionManager()

@app.get("/games")
async def list_games():
    current_time = datetime.now()
    active_games = []
    
    # Clean up expired games
    expired_games = []
    for game_id, game in manager.games.items():
        if current_time - game.created_at > timedelta(minutes=15):
            expired_games.append(game_id)
        elif not game.started:  # Only include non-started games
            active_games.append({
                'game_id': game.game_id,
                'player_count': len(game.player_order),
                'players': [game.player_names.get(p, p) for p in game.player_order],
                'created_at': game.created_at.isoformat()
            })
    
    # Remove expired games and their players
    for game_id in expired_games:
        game = manager.games[game_id]
        for player_id in game.player_order:
            manager.player_to_game.pop(player_id, None)
        del manager.games[game_id]
    
    return {'games': active_games}

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await manager.connect(websocket, player_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["action"] == "set_name":
                player_name = data.get("name", "").strip()
                if not player_name:
                    await websocket.send_json({
                        "action": "error",
                        "message": "Name cannot be empty"
                    })
                    continue
                
                # Store the player's name in their current game if they're in one
                for game in manager.games.values():
                    if player_id in game.players:
                        game.player_names[player_id] = player_name
                        await manager.broadcast_to_game(
                            game.game_id,
                            {
                                "action": "name_updated",
                                "player_id": player_id,
                                "name": player_name,
                                "game_state": game.get_game_state(player_id)
                            }
                        )
                        break
                
                await websocket.send_json({
                    "action": "name_set",
                    "name": player_name
                })
                continue
            
            elif data["action"] == "create_game":
                # Only create a new game if player isn't already in one
                if player_id not in manager.player_to_game:
                    game_id = f"game_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}"
                    game = Game(game_id)
                    game.add_player(player_id)
                    game.player_names[player_id] = player_name
                    
                    manager.games[game_id] = game
                    manager.player_to_game[player_id] = game_id
                    
                    await websocket.send_json({
                        "action": "game_created",
                        "game_id": game_id,
                        "game_state": game.get_game_state(player_id)
                    })
                continue
            
            elif data["action"] == "join_game":
                game_id = data["game_id"]
                if game_id in manager.games:
                    game = manager.games[game_id]
                    if game.add_player(player_id):
                        manager.player_to_game[player_id] = game_id
                        await manager.broadcast_to_game(
                            game_id,
                            {
                                "action": "player_joined",
                                "player_id": player_id,
                                "game_state": game.get_game_state(player_id)
                            }
                        )
                    else:
                        await websocket.send_json({"action": "error", "message": "Cannot join game"})
                else:
                    await websocket.send_json({"action": "error", "message": "Game not found"})
            
            elif data["action"] == "start_game":
                game = manager.get_game_by_player(player_id)
                if not game:
                    continue
                
                # Add AI players if needed
                while len(game.players) < 3:
                    ai_id = game.add_ai_player()
                    await manager.broadcast_to_game(
                        game.game_id,
                        {
                            'action': 'player_joined',
                            'player_id': ai_id,
                            'game_state': game.get_game_state(player_id)
                        }
                    )
                
                game.start_game()
                # Start AI handler in the background
                asyncio.create_task(game.handle_ai_turns())
                
                await manager.broadcast_to_game(
                    game.game_id,
                    {
                        'action': 'game_started',
                        'game_state': game.get_game_state(player_id)
                    }
                )
            
            elif data["action"] == "make_bid":
                game = manager.get_game_by_player(player_id)
                if not game:
                    continue
                
                if game.make_bid(player_id, data["bid"]):
                    await manager.broadcast_to_game(
                        game.game_id,
                        {
                            "action": "bid_made",
                            "player_id": player_id,
                            "bid": data["bid"],
                            "game_state": game.get_game_state(player_id)
                        }
                    )
                else:
                    await websocket.send_json({"action": "error", "message": "Cannot make bid"})
            
            elif data["action"] == "play_card":
                game = manager.get_game_by_player(player_id)
                if not game:
                    continue
                
                if game.play_card(player_id, data["card_index"]):
                    await manager.broadcast_to_game(
                        game.game_id,
                        {
                            "action": "card_played",
                            "player_id": player_id,
                            "card_index": data["card_index"],
                            "game_state": game.get_game_state(player_id)
                        }
                    )
                else:
                    await websocket.send_json({"action": "error", "message": "Cannot play card"})
    
    except WebSocketDisconnect:
        manager.disconnect(player_id)
        game_id = manager.player_to_game.get(player_id)
        if game_id:
            await manager.broadcast_to_game(
                game_id,
                {
                    "action": "player_left",
                    "player_id": player_id
                }
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
