from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import os
import re
import traceback

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
        "default_capacity": 10,
        "peak_hours": ["19:00", "20:00"]
    },
    "messages": { "success": "Confirmé.", "alternative": "Complet.", "failure": "Complet." },
    "reservations": {}, "overrides": {}, "bookings_details": []
}

def load_data():
    if not os.path.exists(DATA_FILE): save_data(default_data); return default_data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            if "bookings_details" not in data: data["bookings_details"] = []
            if "config" not in data: data["config"] = default_data["config"]
            if "reservations" not in data: data["reservations"] = {}
            if "overrides" not in data: data["overrides"] = {}
            return data
    except: return default_data

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
            try: target_date = datetime(year, month, day).strftime("%Y-%m-%d")
            except: pass
        elif day_match:
            day = int(day_match.group(1))
            month = now.month
            year = now.year
            if day < now.day: month += 1
            try: target_date = datetime(year, month, day).strftime("%Y-%m-%d")
            except: pass
        elif bare_number_match and int(bare_number_match.group(1)) <= 31:
            val = int(bare_number_match.group(1))
            if val < 10: 
                day = val; month = now.month; year = now.year
                if day < now.day: month += 1
                try: target_date = datetime(year, month, day).strftime("%Y-%m-%d")
                except: pass
        elif "demain" in text:
            target_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "aujourd'hui" in text:
            target_date = now.strftime("%Y-%m-%d")

        time_match = re.search(r'(\d{1,2})[\:h](\d{2})?', text)
        bare_time = re.search(r'(?:à|vers|^)\s*(\d{1,2})$', text) 
        target_time = None
        if time_match: target_time = f"{int(time_match.group(1)):02d}:00"
        elif bare_time:
            val = int(bare_time.group(1))
            if 10 <= val <= 23: target_time = f"{val:02d}:00"
        
        party_match = re.search(r'(\d+)\s*(p|pers|personnes)', text)
        party_size = None
        if party_match: party_size = int(party_match.group(1))
        elif bare_number_match and not target_date and not target_time:
             val = int(bare_number_match.group(1))
             if val < 10: party_size = val

        return target_date, target_time, party_size

    def get_slot_capacity(self, date, time):
        if date in self.data["overrides"] and time in self.data["overrides"][date]: return self.data["overrides"][date][time]
        return self.data["config"]["default_capacity"]

    def calculate_score(self, target_time, candidate_time, current_load, capacity):
        if capacity == 0: return -1
        fmt = "%H:%M"
        try:
            t_target = datetime.strptime(target_time, fmt)
            t_cand = datetime.strptime(candidate_time, fmt)
            diff_minutes = abs((t_target - t_cand).total_seconds()) / 60
            proximity_score = max(0, 1000 - (diff_minutes * 2)) 
            load_score = (1 - (current_load / capacity)) * 50
            return proximity_score + load_score
        except: return 0

    def find_best_slot(self, date, requested_time, party_size):
        beliefs = self.data["reservations"].get(date, {})
        config = self.data["config"]
        candidates = []
        search_time = requested_time if requested_time else "19:00"
        size_to_check = party_size if party_size else 2

        try: req_h = int(search_time.split(':')[0])
        except: req_h = 19

        for h in range(config["opening_hour"], config["closing_hour"]):
            t_str = f"{h:02d}:00"
            cap = self.get_slot_capacity(date, t_str)
            booked = beliefs.get(t_str, 0)
            
            if (cap - booked) < size_to_check: continue
            if requested_time and t_str == requested_time: return {"time": t_str, "score": 10000, "is_exact": True}
            
            # Filtre : on garde tout dans la journée
            score = self.calculate_score(search_time, t_str, booked, cap)
            candidates.append({"time": t_str, "score": score, "is_exact": False})

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0] if candidates else None

    def analyze_day_status(self, date):
        beliefs = self.data["reservations"].get(date, {})
        config = self.data["config"]
        max_free = 0
        best_time_for_max = None
        for h in range(config["opening_hour"], config["closing_hour"]):
            t_str = f"{h:02d}:00"
            cap = self.get_slot_capacity(date, t_str)
            booked = beliefs.get(t_str, 0)
            free = cap - booked
            if free > max_free:
                max_free = free
                best_time_for_max = t_str
        return max_free, best_time_for_max

    def get_all_available_slots(self, date, party_size):
        beliefs = self.data["reservations"].get(date, {})
        config = self.data["config"]
        available = []
        size_to_check = party_size if party_size else 2
        for h in range(config["opening_hour"], config["closing_hour"]):
            t_str = f"{h:02d}:00"
            cap = self.get_slot_capacity(date, t_str)
            booked = beliefs.get(t_str, 0)
            if (cap - booked) >= size_to_check and cap > 0: available.append(t_str)
        return available

    def commit_booking(self, date, time, size, name="Inconnu", email="Non renseigné"):
        if date not in self.data["reservations"]: self.data["reservations"][date] = {}
        curr = self.data["reservations"][date].get(time, 0)
        self.data["reservations"][date][time] = curr + size
        if "bookings_details" not in self.data: self.data["bookings_details"] = []
        self.data["bookings_details"].append({
            "date": date, "time": time, "name": name, "email": email, "size": size,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_data(self.data)

agent = IntelligentAgent()

# --- API ---la c la partie principale 
# ---  ici 
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
    remaining = cap - booked
    
    # 1. Assez de place ?
    if remaining >= req.party_size:
        agent.commit_booking(req.date, req.time, req.party_size, f"{req.firstname} {req.lastname}", req.email)
        return {"action": "ACCEPT", "message": f"Confirmé à {req.time}."}

    # 2. Sinon, on cherche une alternative
    best = agent.find_best_slot(req.date, req.time, req.party_size)
    
    if not best: 
        return {"action": "REJECT", "message": f"Complet ce jour-là pour {req.party_size} personnes."}

    # 3. Construction du message intelligent
    msg_detail = ""
    if remaining > 0:
        msg_detail = f"Il ne reste que <b>{remaining} place(s)</b> à {req.time}."
    else:
        msg_detail = f"Le créneau de {req.time} est <b>complet</b>."

    return {
        "action": "ALTERNATIVE", 
        "message": f"{msg_detail}<br>Pour <b>{req.party_size} personnes</b>, je propose :", 
        "slot": best["time"]
    }

@app.post("/api/chat")
def chat_with_agent(chat: ChatMessage):
    try:
        cid = chat.client_id
        msg = chat.message.lower().strip()
        
        if msg in ["reset", "stop", "annuler", "recommencer", "restart"]:
            if cid in chat_sessions: del chat_sessions[cid]
            return {"response": "🔄 Conversation réinitialisée. Que puis-je faire pour vous ?"}

        if cid not in chat_sessions: chat_sessions[cid] = {"step": "INITIAL", "data": {}, "memory_date": None}
        session = chat_sessions[cid]
        step = session["step"]

        if step == "WAITING_NEW_DATE":
            if msg in ["non", "no", "non merci", "c'est bon"]:
                session["step"] = "INITIAL"
                return {"response": "Entendu."}
            else:
                session["step"] = "INITIAL" 

        if step == "WAITING_NEW_SIZE":
            match = re.search(r'(\d+)', msg)
            if match:
                size = int(match.group(1))
                session["data"]["size"] = size
                session["step"] = "INITIAL" 
                msg = "" 
            elif msg in ["oui", "yes", "ok"]:
                return {"response": "Entendu. Combien de personnes serez-vous alors ?"}
            elif msg in ["non", "no"]:
                session["step"] = "WAITING_NEW_DATE"
                return {"response": "Ok. Voulez-vous changer de date ?"}
            else:
                return {"response": "Je n'ai pas compris. Donnez-moi un nombre (ex: 4) ou dites Non."}

        if step == "WAITING_SIZE":
            match = re.search(r'(\d+)', msg)
            if match:
                size = int(match.group(1))
                session["data"]["size"] = size
                msg = ""
                step = "INITIAL" 
                session["step"] = "INITIAL"
            else: return {"response": "Je n'ai pas compris le nombre. Combien de personnes ?"}

        if step == "WAITING_CONFIRMATION":
            if msg in ["oui", "yes", "ok", "d'accord", "vas y", "c'est bon"]:
                session["step"] = "WAITING_NAME"
                return {"response": "Entendu. Quel est votre **Nom** ?"}
            elif msg in ["non", "no", "bof", "pas possible"]:
                session["step"] = "WAITING_MORE_OPTIONS"
                return {"response": "D'accord. Voulez-vous voir **toutes** les disponibilités ?"}
            else: step = "INITIAL" 

        if step == "WAITING_MORE_OPTIONS":
            if msg in ["oui", "yes", "montre", "ok", "vas y"]:
                date = session["data"]["date"]
                size = session["data"].get("size", 2)
                slots = agent.get_all_available_slots(date, size)
                session["step"] = "INITIAL"
                session["memory_date"] = date 
                if not slots: return {"response": f"En fait, je n'ai plus rien le {date} pour {size} pers."}
                return {"response": f"Voici les créneaux pour {size} pers :<br>" + ", ".join(slots) + "<br>Lequel voulez-vous ?"}
            else: step = "INITIAL"

        if step == "WAITING_NAME":
            session["data"]["name"] = msg
            session["step"] = "WAITING_EMAIL"
            return {"response": f"Merci {msg}. Quel est votre **Email** ?"}

        if step == "WAITING_EMAIL":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", msg): return {"response": "Email invalide. Réessayez."}
            data = session["data"]
            agent.commit_booking(data["date"], data["time"], data.get("size", 2), data["name"], msg)
            del chat_sessions[cid]
            return {"response": f"🎉 Parfait ! Réservé pour **{data.get('size',2)} pers** le **{data['date']} à {data['time']}**."}

        # ANALYSE
        date, time, size = agent.parse_natural_language(msg)
        
        if not date: date = session.get("memory_date")
        if not date and session["data"].get("date"): date = session["data"]["date"]
        if size: session["data"]["size"] = size
        else: size = session["data"].get("size")

        if not date: return {"response": "Pour quelle **date** souhaitez-vous réserver ?"}
        session["memory_date"] = date 

        if not size:
            session["data"]["date"] = date
            session["data"]["time"] = time
            session["step"] = "WAITING_SIZE"
            return {"response": f"Pour le {date}, vous serez **combien** ?"}

        if not time:
            match = re.search(r'^(\d{1,2})$', msg)
            if match:
                val = int(match.group(1))
                if 10 <= val <= 23: time = f"{val:02d}:00"

        best_slot = agent.find_best_slot(date, time, size)
        
        cap = agent.get_slot_capacity(date, time) if time else 0
        booked = agent.data["reservations"].get(date, {}).get(time, 0) if time else 0
        rem = cap - booked

        if not best_slot: 
            max_free, best_time = agent.analyze_day_status(date)
            if max_free == 0:
                session["step"] = "WAITING_NEW_DATE"
                return {"response": f"❌ Je suis complet toute la journée du {date}.<br>Voulez-vous essayer une **autre date** ?"}
            else:
                session["step"] = "WAITING_NEW_SIZE"
                return {"response": f"⚠️ Je n'ai pas de table pour {size} personnes.<br>Cependant, il me reste **{max_free} place(s)** à {best_time}.<br>Voulez-vous changer la taille du groupe ?"}

        prop_time = best_slot["time"]
        session["data"] = {"date": date, "time": prop_time, "size": size}
        session["step"] = "WAITING_CONFIRMATION"

        if time and prop_time == time: return {"response": f"✅ Disponible : **{date} à {prop_time}** ({size} pers).<br>Je valide ?"}
        elif time: 
            reason = f"⚠️ {time} est complet."
            if rem > 0 and rem < size: reason = f"⚠️ Il ne reste que **{rem} places** à {time}."
            return {"response": f"{reason}<br>Je vous propose **{prop_time}** (pour {size} pers).<br>Ça vous va ?"}
        else: return {"response": f"Pour le {date}, je propose **{prop_time}**.<br>On valide ?"}
    
    except Exception as e:
        traceback.print_exc()
        return {"response": "Une erreur est survenue."}

# Admin
@app.get("/api/admin/data")#@app veut dire application sa represente lapplication fastapi c une technique de decorator en python
def get_admin_data(): return agent.data
@app.post("/api/admin/config")
def upd_conf(c: GlobalConfigUpdate): agent.data["config"].update(c.dict(exclude={'messages'})); agent.data["messages"]=c.messages; save_data(agent.data); return {"status":"ok"}
@app.get("/api/admin/day_details")
def get_day(date: str):
    c = agent.data["config"]
    if date not in agent.data["reservations"]: agent.data["reservations"][date] = {}
    r = agent.data["reservations"][date]
    details = agent.data.get("bookings_details", [])
    output = []
    for h in range(c["opening_hour"], c["closing_hour"]):
        t = f"{h:02d}:00"
        booked_count = r.get(t, 0)
        cap = agent.get_slot_capacity(date, t)
        clients = [{"name": d["name"], "email": d["email"], "size": d["size"]} for d in details if d.get("date") == date and d.get("time") == t]
        output.append({"time": t, "booked": booked_count, "capacity": cap, "available": cap - booked_count, "clients": clients})
    return output
@app.post("/api/admin/update_slot")
def upd_slot(u: AdminSlotUpdate):
    if u.date not in agent.data["overrides"]: agent.data["overrides"][u.date]={}
    agent.data["overrides"][u.date][u.time]=u.capacity
    if u.date not in agent.data["reservations"]: agent.data["reservations"][u.date]={}
    agent.data["reservations"][u.date][u.time]=u.booked
    save_data(agent.data); return {"status":"ok"}