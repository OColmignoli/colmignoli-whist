# Colmignoli Whist

A multiplayer trick-taking card game where players compete in rounds of increasing and decreasing cards, with special no-trump rounds.

## Features

- 3-5 player online gameplay
- Real-time updates using WebSocket
- Secure player connections
- Beautiful card UI
- Game state management

## Game Rules

1. **Setup**:
   - 3-5 players
   - Standard 52-card deck
   - Game progresses in three stages:
     - Ascending (1 card to max possible cards, with trump)
     - No Trump (number of rounds equals number of players)
     - Descending (max cards back to 1, with trump)

2. **Each Round**:
   - Players are dealt cards (starting with 1, increasing each round)
   - Trump card is revealed (except in no-trump rounds)
   - Players bid number of tricks they expect to win
   - Players must follow suit if possible

3. **Scoring**:
   - Correct bid: 10 points + 2 points per trick won
   - Incorrect bid: 2 points per trick won

## Project Structure

```
card_game/
├── backend/
│   ├── src/
│   │   └── main.py         # FastAPI server and game logic
│   ├── tests/              # Backend tests
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx        # Main React component
│   │   └── App.css        # Styles
│   └── package.json       # Frontend dependencies
└── assets/                # Game assets (images, etc.)
```

## Deployment on Render.com

1. Fork this repository to your GitHub account

2. Create a new account on [Render.com](https://render.com) if you haven't already

3. In Render dashboard:
   - Click "New +"
   - Select "Blueprint"
   - Connect your GitHub repository
   - Render will automatically detect the `render.yaml` and create both services

4. Environment Variables:
   The `render.yaml` file will automatically set up most environment variables, but you may need to add:
   - `ENVIRONMENT`: Set to "production"
   - `PORT`: Render will set this automatically

5. Your services will be deployed automatically. Render will provide URLs for both:
   - Backend API: `https://colmignoli-whist-backend.onrender.com`
   - Frontend: `https://colmignoli-whist-frontend.onrender.com`

## Local Development

### Backend
```bash
cd backend
python -m pip install -r requirements.txt
cd src
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm start
```

The game will be available at `http://localhost:3000` and will connect to the backend at `ws://localhost:8000`.

## How to Play

1. Start the game by either creating a new game or joining an existing one using a game ID
2. Wait for 3-5 players to join
3. Once enough players have joined, the game can be started
4. Each player receives 5 cards
5. Players take turns playing cards
6. Follow the on-screen instructions for gameplay

## Development

The game uses:
- FastAPI for the backend server
- WebSockets for real-time communication
- React with TypeScript for the frontend
- Modern CSS for styling

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Submit a pull request

## License

MIT License
