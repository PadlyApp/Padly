cd backend

python3 -m venv venv

pip install -r requirements.txt

-----------------------------------
WINDOWS: .\venv\Scripts\activate
MAC/LINUX: venv/bin/activate
-----------------------------------

uvicorn app.main:app --reload
