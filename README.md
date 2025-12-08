<img width="1896" height="992" alt="SCR-20251207-pvrw" src="https://github.com/user-attachments/assets/8c0c27b1-bdc2-40af-aa2e-8cfc96ca8d4c" />
<img width="1897" height="972" alt="SCR-20251207-pvpu" src="https://github.com/user-attachments/assets/e2dfc67d-aa8d-4025-9bb5-bdc502412dcf" />


ArenaSignage – Dashboard & Player Agent

Modern Raspberry Pi digital signage platform.

This project contains:

🖥️ Backend API (FastAPI + PostgreSQL)

Handles players, playlists, items, assignment logic and effective playlist computation.

🌐 Dashboard (HTML + JS + CSS)

Web-based control panel with Tesla-style UI for managing signage devices and playlists.

🍓 Player Agent (coming soon)

2. Quick Start Using Docker (recommended)
   
Clone the repository:

git clone https://github.com/TheElementOfLif3/arena-signage-agent.git
cd arena-signage-agent

Start backend + PostgreSQL:

docker compose up -d

Check logs:

docker logs -f arena-signage-backend

Dashboard is now available at:

👉 http://localhost:8000/dashboard

API root is available at:

👉 http://localhost:8000

Interactive API docs (Swagger):

👉 http://localhost:8000/docs


3. Run Without Docker (local Python environment)
   
Install dependencies:

pip install -r requirements.txt

Run FastAPI server:

uvicorn app.main:app --reload

Open in browser:

👉 http://localhost:8000/dashboard

🗂️ Project Structure

<img width="435" height="263" alt="SCR-20251207-rpdk" src="https://github.com/user-attachments/assets/d1f2789d-e89d-411b-b01f-7c4d871e600c" />


🧪 4. Test Data (Optional)

Run this SQL inside PostgreSQL container:

docker exec -it arena-signage-db-1 psql -U postgres

Create example playlist:

INSERT INTO playlists (id, name, description, is_active)
VALUES (1, 'Test', 'Demo playlist', true);

🎯 5. Roadmap
	•	Raspberry Pi Player Agent (full-screen playback)
	•	Web-based playlist editor
	•	Group-based player assignment
	•	Remote live preview
	•	Cloud deployment templates

⸻

📝 6. License

This project is licensed under the MIT License.



   
