from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "agent_data.json"
chat_sessions = {} 

default_data = {
    "config": {
        "opening_hour": 11,
        "closing_hour": 23,
        "default_capacity": 4,
        "peak_hours": ["19:00", "20:00"]
    },
    "messages": { "success": "Confirmé.", "alternative": "Complet.", "failure": "Complet." },
    "reservations": {}, "overrides": {}, "bookings_details": []
}

def load_data():
    if not os.path.exists(DATA_FILE): save_data(default_data); return default_data
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        if "bookings_details" not in data: data["bookings_details"] = []
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=4)

# --- MODÈLES ---
class ReservationRequest(BaseModel):
    date: str; time: str; firstname: str; lastname: str; email: str; party_size: int
class ChatMessage(BaseModel): message: str; client_id: str
class SlotOverride(BaseModel): date: str; time: str; capacity: int
class GlobalConfigUpdate(BaseModel): opening_hour: int; closing_hour: int; default_capacity: int; messages: Dict[str, str]
class AdminSlotUpdate(BaseModel): date: str; time: str; booked: int; capacity: int

# --- IA ENGINE ---
class IntelligentAgent:
    def __init__(self): self.data = load_data()

    def parse_natural_language(self, text):
        text = text.lower().strip()
        now = datetime.now()
        target_date = None

        full_date_match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})', text)
        day_match = re.search(r'\b(?:le|au)\s+(\d{1,2})\b', text)
        bare_number_match = re.match(r'^(\d{1,2})$', text)

        if full_date_match:
            day, month = int(full_date_match.group(1)), int(full_date_match.group(2))
            year = now.year
            if month < now.month: year += 1
            target_date = datetime(year, month, day).strftime("%Y-%m-%d")
        elif day_match:
            day = int(day_match.group(1))
            month = now.month
            year = now.year
            if day < now.day: month += 1
            target_date = datetime(year, month, day).strftime("%Y-%m-%d")
        elif bare_number_match and int(bare_number_match.group(1)) <= 31:
            val = int(bare_number_match.group(1))
            if val < 10: # Si c'est un petit chiffre, c'est surement une date
                day = val; month = now.month; year = now.year
                if day < now.day: month += 1
                target_date = datetime(year, month, day).strftime("%Y-%m-%d")
        elif "demain" in text:
            target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "aujourd'hui" in text:
            target_date = now.strftime("%Y-%m-%d")

        time_match = re.search(r'(\d{1,2})[\:h](\d{2})?', text)
        bare_time = re.search(r'(?:à|vers|^)\s*(\d{1,2})$', text) 
        target_time = None
        
        if time_match:
            target_time = f"{int(time_match.group(1)):02d}:00"
        elif bare_time:
            val = int(bare_time.group(1))
            if 10 <= val <= 23: target_time = f"{val:02d}:00"
        
        party_match = re.search(r'(\d+)\s*(p|pers|personnes)', text)
        party_size = int(party_match.group(1)) if party_match else 2

        return target_date, target_time, party_size

    def get_slot_capacity(self, date, time):
        if date in self.data["overrides"] and time in self.data["overrides"][date]: return self.data["overrides"][date][time]
        return self.data["config"]["default_capacity"]

    def calculate_score(self, target_time, candidate_time, current_load, capacity):
        if capacity == 0: return -1
        fmt = "%H:%M"
        t_target = datetime.strptime(target_time, fmt)
        t_cand = datetime.strptime(candidate_time, fmt)
        diff_minutes = abs((t_target - t_cand).total_seconds()) / 60
        
        if diff_minutes > 180: return 0 
        proximity_score = max(0, 100 - (diff_minutes * 0.5))
        load_score = (1 - (current_load / capacity)) * 100
        return (proximity_score * 0.7) + (load_score * 0.3)

    def find_best_slot(self, date, requested_time, party_size):
        beliefs = self.data["reservations"].get(date, {})
        config = self.data["config"]
        candidates = []
        
        # CORRECTION : Si pas d'heure demandée, on ne filtre pas les heures !
        # On utilise 19h juste pour le "score" de préférence, mais on accepte tout.
        search_time = requested_time if requested_time else "19:00"
        
        for h in range(config["opening_hour"], config["closing_hour"]):
            t_str = f"{h:02d}:00"
            cap = self.get_slot_capacity(date, t_str)
            booked = beliefs.get(t_str, 0)
            
            # 1. Exact Match : Si le client demande une heure précise et qu'elle est dispo
            if requested_time and t_str == requested_time and (cap - booked) >= party_size and cap > 0:
                return {"time": t_str, "score": 1000, "is_exact": True}
            
            # 2. Filtrage : On filtre l'écart SEULEMENT si une heure a été explicitement demandée
            if requested_time:
                req_h = int(requested_time.split(':')[0])
                if abs(h - req_h) > 4: continue

            # 3. Calcul Score
            score = self.calculate_score(search_time, t_str, booked, cap)
            
            # On accepte tout créneau où il y a de la place
            if (cap - booked) >= party_size and cap > 0:
                candidates.append({"time": t_str, "score": score, "is_exact": False})

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0] if candidates else None

    def get_all_available_slots(self, date, party_size):
        beliefs = self.data["reservations"].get(date, {})
        config = self.data["config"]
        available = []
        for h in range(config["opening_hour"], config["closing_hour"]):
            t_str = f"{h:02d}:00"
            cap = self.get_slot_capacity(date, t_str)
            booked = beliefs.get(t_str, 0)
            if (cap - booked) >= party_size and cap > 0: available.append(t_str)
        return available

    def commit_booking(self, date, time, size, name="Inconnu", email="Non renseigné"):
        if date not in self.data["reservations"]: self.data["reservations"][date] = {}
        curr = self.data["reservations"][date].get(time, 0)
        self.data["reservations"][date][time] = curr + size
        self.data["bookings_details"].append({
            "date": date, "time": time, "name": name, "email": email, "size": size,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data(self.data)

agent = IntelligentAgent()

# --- API ---
@app.get("/api/slots")
def get_slots(date: str):
    config = agent.data["config"]
    reservations = agent.data["reservations"].get(date, {})
    slots = []
    for h in range(config["opening_hour"], config["closing_hour"]):
        t = f"{h:02d}:00"
        cap = agent.get_slot_capacity(date, t)
        booked = reservations.get(t, 0)
        slots.append({"time": t, "available": max(0, cap - booked), "full": (cap - booked) <= 0})
    return slots

@app.post("/api/reserve")
def reserve(req: ReservationRequest):
    cap = agent.get_slot_capacity(req.date, req.time)
    booked = agent.data["reservations"].get(req.date, {}).get(req.time, 0)
    
    if (cap - booked) >= req.party_size and cap > 0:
        agent.commit_booking(req.date, req.time, req.party_size, f"{req.firstname} {req.lastname}", req.email)
        return {"action": "ACCEPT", "message": f"Confirmé à {req.time}.", "slot": req.time}

    best = agent.find_best_slot(req.date, req.time, req.party_size)
    if not best: return {"action": "REJECT", "message": "Complet ce jour-là."}
    return {"action": "ALTERNATIVE", "message": "Ce créneau n'est plus dispo. Je propose :", "slot": best["time"]}

@app.post("/api/chat")
def chat_with_agent(chat: ChatMessage):
    cid = chat.client_id
    msg = chat.message.lower().strip()
    
    if cid not in chat_sessions: chat_sessions[cid] = {"step": "INITIAL", "data": {}, "memory_date": None}
    session = chat_sessions[cid]
    step = session["step"]

    # 1. Négociation
    if step == "WAITING_CONFIRMATION":
        if msg in ["oui", "yes", "ok", "d'accord", "vas y", "c'est bon"]:
            session["step"] = "WAITING_NAME"
            return {"response": "Entendu. Quel est votre **Nom** ?"}
        elif msg in ["non", "no", "bof"]:
            session["step"] = "WAITING_MORE_OPTIONS"
            return {"response": "D'accord. Voulez-vous voir **toutes** les disponibilités ?"}
        else:
            step = "INITIAL" 

    # 2. Liste
    if step == "WAITING_MORE_OPTIONS":
        if msg in ["oui", "yes", "montre", "ok", "vas y"]:
            date = session["data"]["date"]
            size = session["data"]["size"]
            slots = agent.get_all_available_slots(date, size)
            session["step"] = "INITIAL"
            session["memory_date"] = date 
            if not slots: return {"response": f"En fait, je n'ai plus rien le {date}."}
            return {"response": f"Voici les créneaux du {date} :<br>" + ", ".join(slots) + "<br>Lequel voulez-vous ?"}
        else:
            step = "INITIAL"

    # 3. Nom
    if step == "WAITING_NAME":
        session["data"]["name"] = msg
        session["step"] = "WAITING_EMAIL"
        return {"response": f"Merci {msg}. Quel est votre **Email** ?"}

    # 4. Email
    if step == "WAITING_EMAIL":
        if not re.match(r"[^@]+@[^@]+\.[^@]+", msg): return {"response": "Email invalide. Réessayez."}
        data = session["data"]
        agent.commit_booking(data["date"], data["time"], data["size"], data["name"], msg)
        del chat_sessions[cid]
        return {"response": f"🎉 Parfait ! Réservé au nom de **{data['name']}** (<small>{msg}</small>) pour le **{data['date']} à {data['time']}**."}

    # 0. ANALYSE (INITIAL)
    date, time, size = agent.parse_natural_language(msg)
    
    if not date and not session["memory_date"]:
        return {"response": "Je n'ai pas bien compris la date. Pouvez-vous reformuler ?<br><i>Exemple : 'le 5' ou 'demain à 20h'</i>"}
    
    if not date: date = session["memory_date"]
    else: session["memory_date"] = date

    if not time:
        match = re.search(r'^(\d{1,2})$', msg)
        if match:
            val = int(match.group(1))
            if 10 <= val <= 23: time = f"{val:02d}:00"

    best_slot = agent.find_best_slot(date, time, size)
    
    if not best_slot: return {"response": f"❌ Désolé, je suis complet le {date}."}

    prop_time = best_slot["time"]
    session["data"] = {"date": date, "time": prop_time, "size": size}
    session["step"] = "WAITING_CONFIRMATION"

    if time and prop_time == time:
        return {"response": f"✅ Disponible : **{date} à {prop_time}** ({size} pers).<br>Je valide ?"}
    elif time:
        return {"response": f"⚠️ {time} est complet le {date}.<br>Je vous propose **{prop_time}**.<br>Ça vous va ?"}
    else:
        return {"response": f"Pour le {date}, je propose **{prop_time}**.<br>On valide ?"}

# Admin
@app.get("/api/admin/data")
def get_admin_data(): return agent.data
@app.post("/api/admin/config")
def upd_conf(c: GlobalConfigUpdate): agent.data["config"].update(c.dict(exclude={'messages'})); agent.data["messages"]=c.messages; save_data(agent.data); return {"status":"ok"}
@app.get("/api/admin/day_details")
def get_day(date: str):
    c = agent.data["config"]
    r = agent.data["reservations"].get(date, {})
    details = agent.data.get("bookings_details", [])
    output = []
    for h in range(c["opening_hour"], c["closing_hour"]):
        t = f"{h:02d}:00"
        booked_count = r.get(t, 0)
        cap = agent.get_slot_capacity(date, t)
        clients = [{"name": d["name"], "email": d["email"], "size": d["size"]} for d in details if d["date"] == date and d["time"] == t]
        output.append({"time": t, "booked": booked_count, "capacity": cap, "available": cap - booked_count, "clients": clients})
    return output
@app.post("/api/admin/update_slot")
def upd_slot(u: AdminSlotUpdate):
    if u.date not in agent.data["overrides"]: agent.data["overrides"][u.date]={}
    agent.data["overrides"][u.date][u.time]=u.capacity
    if u.date not in agent.data["reservations"]: agent.data["reservations"][u.date]={}
    agent.data["reservations"][u.date][u.time]=u.booked
    save_data(agent.data); return {"status":"ok"}