import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

interface Card {
  suit: string;
  value: string;
}

interface GameState {
  game_id: string;
  players: string[];
  player_names: { [key: string]: string };
  current_player: string;
  your_cards: Card[];
  cards_per_player: { [key: string]: number };
  started: boolean;
  phase: string;
  trump_card: Card | null;
  bids: { [key: string]: number };
  tricks_won: { [key: string]: number };
  scores: { [key: string]: number };
  current_round: { [key: string]: Card };
  led_suit: string | null;
  round_number: number;
  cards_per_round: number;
  game_stage: string;
  no_trump_rounds_played: number;
}

interface GameListing {
  game_id: string;
  player_count: number;
  players: string[];
  created_at: string;
}

function App() {
  const [playerId] = useState(`player_${Math.random().toString(36).substr(2, 9)}`);
  const [playerName, setPlayerName] = useState('');
  const [isNameSet, setIsNameSet] = useState(false);
  const [availableGames, setAvailableGames] = useState<GameListing[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [gameId, setGameId] = useState<string>('');
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string>('');
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  const handleServerMessage = useCallback((data: any) => {
    switch (data.action) {
      case 'game_created':
        setGameId(data.game_id);
        break;
      case 'player_joined':
      case 'game_started':
      case 'bid_made':
      case 'card_played':
        setGameState(data.game_state);
        break;
      case 'error':
        setError(data.message);
        break;
      case 'player_left':
        if (gameState) {
          setGameState({
            ...gameState,
            players: gameState.players.filter(p => p !== data.player_id)
          });
        }
        break;
      case 'name_set':
        setIsNameSet(true);
        break;
      case 'name_updated':
        if (gameState) {
          setGameState(data.game_state);
        }
        break;
    }
  }, [gameState, setGameState, setError, setGameId]);

  useEffect(() => {
    let apiUrl = process.env.REACT_APP_API_URL;
    if (!apiUrl) {
      console.error('REACT_APP_API_URL is not set');
      setError('API URL not configured');
      setConnectionStatus('disconnected');
      return;
    }
    console.log('API URL:', apiUrl);

    // Ensure the URL uses HTTPS in production
    if (process.env.NODE_ENV === 'production' && apiUrl.startsWith('http://')) {
      apiUrl = apiUrl.replace('http://', 'https://');
    }

    // Convert http:// or https:// to ws:// or wss:// respectively
    const wsUrl = apiUrl.replace(/^http/, 'ws').replace(/^https/, 'wss');
    console.log('Attempting WebSocket connection to:', wsUrl);
    setConnectionStatus('connecting');

    try {
      const websocket = new WebSocket(`${wsUrl}/ws/${playerId}`);
      
      websocket.onopen = () => {
        console.log('WebSocket connection established');
        setWs(websocket);
        setConnectionStatus('connected');
        setError(''); // Clear any previous connection errors
      };

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('Received message:', data);
          handleServerMessage(data);
        } catch (e) {
          console.error('Error parsing WebSocket message:', e);
          setError('Error processing server message');
        }
      };

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Failed to connect to server. Please try refreshing the page.');
        setConnectionStatus('disconnected');
      };

      websocket.onclose = () => {
        console.log('WebSocket connection closed');
        setConnectionStatus('disconnected');
        setWs(null);
      };

      return () => {
        websocket.close();
      };
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      setError('Failed to create WebSocket connection');
      setConnectionStatus('disconnected');
    }
  }, [playerId, handleServerMessage]);

  const createGame = useCallback(() => {
    if (ws) {
      ws.send(JSON.stringify({ action: 'create_game' }));
    }
  }, [ws]);

  const joinGame = useCallback((gameIdToJoin: string) => {
    if (ws) {
      ws.send(JSON.stringify({ action: 'join_game', game_id: gameIdToJoin }));
    }
  }, [ws]);

  const startGame = useCallback(() => {
    if (ws) {
      ws.send(JSON.stringify({ action: 'start_game' }));
    }
  }, [ws]);

  const makeBid = useCallback((bid: number) => {
    if (ws) {
      ws.send(JSON.stringify({ action: 'make_bid', bid }));
    }
  }, [ws]);

  const playCard = useCallback((cardIndex: number) => {
    if (ws) {
      ws.send(JSON.stringify({ action: 'play_card', card_index: cardIndex }));
    }
  }, [ws]);

  const fetchGames = useCallback(async () => {
    try {
      const apiUrl = process.env.REACT_APP_API_URL;
      if (!apiUrl) {
        console.error('REACT_APP_API_URL is not set');
        return;
      }
      const response = await fetch(`${apiUrl}/games`);
      const data = await response.json();
      setAvailableGames(data.games);
    } catch (error) {
      console.error('Error fetching games:', error);
    }
  }, []);

  useEffect(() => {
    if (!gameState) {
      fetchGames();
      const interval = setInterval(fetchGames, 5000); // Refresh every 5 seconds
      return () => clearInterval(interval);
    }
  }, [fetchGames, gameState]);

  const setName = useCallback(() => {
    if (ws && playerName.trim()) {
      ws.send(JSON.stringify({ 
        action: 'set_name', 
        name: playerName.trim() 
      }));
      setIsNameSet(true);
    }
  }, [ws, playerName]);

  const renderCard = (card: Card) => (
    <div className="card">
      <div className={`suit ${card.suit}`}>
        {card.value} of {card.suit}
      </div>
    </div>
  );

  return (
    <div className="App">
      <div className="connection-status" style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '8px 15px',
        borderRadius: '8px',
        backgroundColor: connectionStatus === 'connected' ? '#4CAF50' : 
                       connectionStatus === 'connecting' ? '#FFA500' : '#f44336',
        color: 'white',
        fontSize: '16px',
        fontWeight: 'bold',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        zIndex: 1000
      }}>
        {connectionStatus === 'connected' ? '🟢 Connected' : 
         connectionStatus === 'connecting' ? '🟡 Connecting...' : '🔴 Disconnected'}
      </div>
      <header className="App-header">
        <h1>Trick-Taking Card Game</h1>
        {error && <div className="error">{error}</div>}
      </header>
      
      <main>
        {!isNameSet ? (
          <div className="name-setup">
            <h2>Welcome to Whist!</h2>
            <div className="name-input">
              <input
                type="text"
                placeholder="Enter your name"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && setName()}
              />
              <button onClick={setName} disabled={!playerName.trim()}>
                Set Name
              </button>
            </div>
          </div>
        ) : !gameState && (
          <div className="game-setup">
            <button onClick={createGame}>Create New Game</button>
            
            <div className="available-games">
              <h3>Available Games</h3>
              {availableGames.length === 0 ? (
                <p>No games available. Create one!</p>
              ) : (
                <div className="games-list">
                  {availableGames.map(game => (
                    <div key={game.game_id} className="game-item">
                      <div className="game-info">
                        <span>Players: {game.players.join(', ')}</span>
                        <span>{game.player_count}/5 players</span>
                      </div>
                      <button onClick={() => joinGame(game.game_id)}>
                        Join Game
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="join-game">
              <input
                type="text"
                placeholder="Or enter Game ID"
                onChange={(e) => setGameId(e.target.value)}
                value={gameId}
              />
              <button onClick={() => joinGame(gameId)}>Join Game</button>
            </div>
          </div>
        )}

        {gameState && (
          <div className="game-board">
            <div className="game-info">
              <p>Game ID: {gameState.game_id}</p>
              <p>Players: {gameState.players.map(p => (
                <span key={p} className={p.startsWith('ai_player') ? 'ai-player' : ''}>
                  {gameState.player_names[p] || p}
                  {p.startsWith('ai_player') && ' 🤖'}
                </span>
              )).reduce((prev, curr) => [prev, ', ', curr])}</p>
              <p>Current Player: {
                gameState.current_player.startsWith('ai_player') ? 
                `${gameState.player_names[gameState.current_player]} 🤖 (thinking...)` :
                gameState.player_names[gameState.current_player] || gameState.current_player
              }</p>
              <p>Phase: {gameState.phase}</p>
              <p>
                Round: {gameState.round_number} ({gameState.cards_per_round} cards)
                {gameState.game_stage === "no_trump" && 
                  ` - No Trump Round ${gameState.no_trump_rounds_played + 1}/${gameState.players.length}`
                }
              </p>
              <p>Stage: {
                gameState.game_stage === "ascending" ? "Ascending (with trump)" :
                gameState.game_stage === "no_trump" ? "No Trump" :
                "Descending (with trump)"
              }</p>
              {gameState.trump_card && gameState.game_stage !== "no_trump" && (
                <div className="trump-card">
                  <h3>Trump Card:</h3>
                  {renderCard(gameState.trump_card)}
                </div>
              )}
            </div>

            {gameState.phase === 'waiting' && (
              <button 
                onClick={startGame} 
                disabled={gameState.players.length < 1}
              >
                Start Game (AI will fill empty slots)
              </button>
            )}

            {gameState.phase === 'bidding' && gameState.current_player === playerId && (
              <div className="bidding">
                <h3>Make your bid (0-{gameState.cards_per_round}):</h3>
                <div className="bid-buttons">
                  {Array.from({length: gameState.cards_per_round + 1}, (_, i) => (
                    <button key={i} onClick={() => makeBid(i)}>
                      Bid {i}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {gameState.phase === 'playing' && (
              <>
                <div className="current-round">
                  <h3>Current Trick:</h3>
                  <div className="played-cards">
                    {Object.entries(gameState.current_round).map(([pid, card]) => (
                      <div key={pid} className="played-card">
                        <p>{pid}</p>
                        {renderCard(card)}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="player-cards">
                  <h3>Your Cards:</h3>
                  <div className="cards">
                    {gameState.your_cards.map((card, index) => (
                      <div
                        key={index}
                        onClick={() => gameState.current_player === playerId && playCard(index)}
                        className={`card ${gameState.current_player === playerId ? 'playable' : ''}`}
                      >
                        {renderCard(card)}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            {gameState.phase === 'game_over' && (
              <div className="game-over">
                <h2>Game Over!</h2>
                <p>Winner: {
                  Object.entries(gameState.scores)
                    .reduce((a, b) => a[1] > b[1] ? a : b)[0]
                }</p>
              </div>
            )}

            <div className="scores">
              <h3>Scores and Bids</h3>
              {Object.entries(gameState.scores).map(([pid, score]) => {
                const bid = gameState.bids[pid];
                const tricks = gameState.tricks_won[pid];
                const roundComplete = gameState.phase === 'round_over';
                const bidCorrect = bid === tricks;
                
                return (
                  <div key={pid} className={`player-score ${roundComplete && bidCorrect ? 'correct-bid' : ''}`}>
                    <p className="player-name">{pid}</p>
                    <p className="score-details">
                      Total Score: {score} points
                      {gameState.phase !== 'waiting' && (
                        <>
                          <br />
                          Bid: {bid ?? '?'} | Tricks: {tricks}
                          {roundComplete && (
                            <span className="round-points">
                              (+{bidCorrect ? 
                                `${10 + (tricks * 2)} points: 10 + ${tricks}×2` : 
                                `${tricks * 2} points: ${tricks}×2`})
                            </span>
                          )}
                        </>
                      )}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
