import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

interface Card {
  suit: string;
  value: string;
}

interface GameState {
  game_id: string;
  players: string[];
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

function App() {
  const [playerId] = useState(`player_${Math.random().toString(36).substr(2, 9)}`);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [gameId, setGameId] = useState<string>('');
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const apiUrl = process.env.REACT_APP_API_URL || 'ws://localhost:8000';
    // Convert http:// or https:// to ws:// or wss:// respectively
    const wsUrl = apiUrl.replace(/^http/, 'ws');
    const websocket = new WebSocket(`${wsUrl}/ws/${playerId}`);
    
    websocket.onopen = () => {
      console.log('Connected to server');
      setWs(websocket);
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleServerMessage(data);
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setError('Failed to connect to server');
    };

    return () => {
      websocket.close();
    };
  }, [playerId]);

  const handleServerMessage = (data: any) => {
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
    }
  };

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

  const renderCard = (card: Card) => (
    <div className="card">
      <div className={`suit ${card.suit}`}>
        {card.value} of {card.suit}
      </div>
    </div>
  );

  return (
    <div className="App">
      <header className="App-header">
        <h1>Trick-Taking Card Game</h1>
        {error && <div className="error">{error}</div>}
      </header>
      
      <main>
        {!gameState && (
          <div className="game-setup">
            <button onClick={createGame}>Create New Game</button>
            <div className="join-game">
              <input
                type="text"
                placeholder="Enter Game ID"
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
              <p>Players: {gameState.players.join(', ')}</p>
              <p>Current Player: {gameState.current_player}</p>
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
                disabled={gameState.players.length < 3}
              >
                Start Game ({gameState.players.length}/3-5 players)
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
