"""Measured, scenario-backed career missions for ASTRA's native Gioca mode."""
from __future__ import annotations

from copy import deepcopy
import math


MISSIONS = {
    "space": [
        {"id": "space_skyward", "vehicle": "space", "scenario": "mission",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · I / VI",
         "title": "SKYWARD · Orbita al primo tentativo",
         "briefing": "CONTROLLO MISSIONE: la finestra di lancio è aperta per pochi minuti. Porta il vettore oltre la linea di Kármán, mantieni il corridoio di ascesa e conserva il margine di propellente per la sequenza di inserzione.",
         "objectives": [{"type": "altitude", "value": 120000, "label": "Raggiungi 120 km"}],
         "reward": {"credits": 18000, "reputation": 12, "science": 8}},
        {"id": "space_pulsar", "vehicle": "space", "scenario": "orbital",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · II / VI",
         "title": "PULSAR · Rendezvous in LEO",
         "briefing": "Una capsula di rifornimento ha perso la guida autonoma. Intercetta il bersaglio con impulsi RCS progressivi, controlla la velocità relativa e fermati nel corridoio di prossimità prima del contatto.",
         "objectives": [{"type": "rendezvous", "range_m": 30, "speed_m_s": 0.3,
                         "label": "≤30 m e ≤0,3 m/s dal bersaglio"}],
         "reward": {"credits": 24000, "reputation": 16, "science": 12}},
        {"id": "space_depot", "vehicle": "space", "scenario": "orbital",
         "category": "INGEGNERIA", "campaign": "FRONTIERA BLU · III / VI",
         "title": "WAYFARER · Aggancio al deposito orbitale",
         "briefing": "Il deposito ha energia limitata e una finestra di aggancio. Allinea il veicolo sul corridoio finale, annulla la deriva relativa e completa un rendezvous stabile senza superare il limite di contatto.",
         "objectives": [{"type": "rendezvous", "range_m": 5, "speed_m_s": 0.1,
                         "label": "Stabilizza entro 5 m e 0,1 m/s"}],
         "reward": {"credits": 30000, "reputation": 20, "science": 15}},
        {"id": "space_selene", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · IV / VI",
         "title": "SELENE · Discesa di precisione",
         "briefing": "La base lunare attende un lander prima del passaggio notturno. Leggi la velocità di discesa, frena con anticipo e posa il veicolo senza danneggiare antenne o carico scientifico.",
         "objectives": [{"type": "safe_landing", "speed_m_s": 3.0,
                         "label": "Atterra a ≤3 m/s"}],
         "reward": {"credits": 21000, "reputation": 14, "science": 16}},
        {"id": "space_shackleton", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · V / VI",
         "title": "SHACKLETON · Stazione di misura polare",
         "briefing": "La squadra robotica ha localizzato ghiaccio vicino al bordo del cratere. Mantieni il lander nella fascia di campionamento per acquisire una misura stabile, poi scendi nel sito sicuro prima che la luce svanisca.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 90, "maximum_m": 140,
                         "seconds": 6, "label": "Mantieni 90–140 m per 6 s"},
                        {"type": "safe_landing", "speed_m_s": 1.5,
                         "label": "Atterra nel sito a ≤1,5 m/s"}],
         "reward": {"credits": 27000, "reputation": 19, "science": 24}},
        {"id": "space_vesta", "vehicle": "space", "scenario": "planetary",
         "category": "ESPLORAZIONE", "campaign": "FRONTIERA BLU · VI / VI",
         "title": "VESTA · Deposito del contenitore campioni",
         "briefing": "Ultima discesa della spedizione: consegna il contenitore al sito di raccolta e conserva il veicolo per la missione di rientro. Il contatto deve essere dolce e l'assetto stabile durante l'ultima finestra di misura.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 30, "maximum_m": 55,
                         "seconds": 10, "label": "Stabilizza 30–55 m per 10 s"},
                        {"type": "safe_landing", "speed_m_s": 1.0,
                         "label": "Completa il touchdown a ≤1 m/s"}],
         "reward": {"credits": 34000, "reputation": 24, "science": 30}},
    ],
    "aircraft": [
        {"id": "air_blue_line", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · I / III",
         "title": "BLUE LINE · Circuito completo",
         "briefing": "Il collaudo inaugurale viene seguito in diretta dalla torre. Decolla, porta il velivolo in quota sul circuito costiero e rientra sulla pista entro il limite di velocità di contatto.",
         "objectives": [{"type": "altitude", "value": 700, "label": "Raggiungi 700 m"},
                        {"type": "distance", "value": 12000, "label": "Vola 12 km"},
                        {"type": "safe_landing", "speed_m_s": 35, "label": "Rientra e atterra in sicurezza"}],
         "reward": {"credits": 8500, "reputation": 8, "science": 2}},
        {"id": "air_alpine", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · II / III",
         "title": "ALPINE WINDOW · Rotta in quota",
         "briefing": "Una perturbazione chiude il corridoio basso. Attraversa la finestra di quota lungo la rotta alpina, mantieni il controllo in aria rarefatta e riporta il velivolo alla base.",
         "objectives": [{"type": "altitude", "value": 2200, "label": "Raggiungi 2.200 m"},
                        {"type": "distance", "value": 30000, "label": "Completa 30 km"},
                        {"type": "safe_landing", "speed_m_s": 42, "label": "Atterra sotto 42 m/s"}],
         "reward": {"credits": 14000, "reputation": 13, "science": 4}},
        {"id": "air_recovery", "vehicle": "aircraft", "scenario": "mission",
         "category": "PILOTAGGIO", "campaign": "COLLAUDO ATMOSFERICO · III / III",
         "title": "RUNWAY 27 · Rientro stretto",
         "briefing": "Il vento in coda ha ridotto la lunghezza utile della pista. Esegui il circuito compatto, stabilizza l'avvicinamento e atterra entro il limite; portanza, stallo e touchdown sono valutati dal modello 6-DoF.",
         "objectives": [{"type": "altitude", "value": 350, "label": "Supera 350 m"},
                        {"type": "distance", "value": 5000, "label": "Completa 5 km"},
                        {"type": "safe_landing", "speed_m_s": 27, "label": "Atterra sotto 27 m/s"}],
         "reward": {"credits": 10000, "reputation": 10, "science": 3}},
    ],
    "drone": [
        {"id": "drone_grid", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · I / III",
         "title": "GRID 04 · Ispezione della linea",
         "briefing": "Una tempesta ha interrotto il monitoraggio della linea elettrica. Acquisisci una traccia continua lungo il corridoio, mantieni la quota di campionamento e rientra con energia sufficiente per l'atterraggio.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 25, "maximum_m": 80,
                         "seconds": 12, "label": "Resta tra 25 e 80 m per 12 s"},
                        {"type": "distance", "value": 250, "label": "Percorri 250 m"},
                        {"type": "safe_landing", "speed_m_s": 1.5, "label": "Rientra e atterra"}],
         "reward": {"credits": 4200, "reputation": 7, "science": 6}},
        {"id": "drone_tower", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · II / III",
         "title": "TOWER ECHO · Controllo strutturale",
         "briefing": "Il sensore acustico ha rilevato vibrazioni anomale sulla torre. Mantieni una quota ravvicinata ma sicura per completare la finestra di acquisizione, poi torna al pad senza urti.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 15, "maximum_m": 45,
                         "seconds": 18, "label": "Completa 18 s nella fascia 15–45 m"},
                        {"type": "safe_landing", "speed_m_s": 1.2, "label": "Atterra senza urti"}],
         "reward": {"credits": 5800, "reputation": 9, "science": 9}},
        {"id": "drone_med", "vehicle": "drone", "scenario": "mission",
         "category": "SCIENZA", "campaign": "OCCHI SULLA TERRA · III / III",
         "title": "AEROSOL-3 · Profilo atmosferico",
         "briefing": "Una sonda a terra ha perso il sensore meteo. Vola la tratta di campionamento a quota costante, completa la finestra di misura e recupera il drone sul pad con il pacco dati integro.",
         "objectives": [{"type": "hold_altitude", "minimum_m": 45, "maximum_m": 70,
                         "seconds": 20, "label": "Campiona tra 45 e 70 m per 20 s"},
                        {"type": "distance", "value": 350, "label": "Completa la tratta di 350 m"},
                        {"type": "safe_landing", "speed_m_s": 1.5, "label": "Recupera sul pad a ≤1,5 m/s"}],
         "reward": {"credits": 8500, "reputation": 12, "science": 14}},
    ],
}


def mission_catalog(vehicle: str | None = None) -> dict:
    if vehicle is not None and vehicle not in MISSIONS:
        raise ValueError("Choose space, aircraft or drone")
    return {key: deepcopy(value) for key, value in MISSIONS.items()
            if vehicle is None or key == vehicle}


def find_mission(mission_id: str) -> dict:
    for missions in MISSIONS.values():
        for mission in missions:
            if mission["id"] == mission_id:
                return deepcopy(mission)
    raise ValueError("Gioca mission not found")


class GameSession:
    def __init__(self) -> None:
        self.mission: dict | None = None
        self.progress: dict = {}
        self.elapsed_s = 0.0
        self.distance_m = 0.0
        self.hold_s = 0.0
        self.previous_position: list[float] | None = None
        self.last_time_s: float | None = None
        self.complete = False

    def start(self, mission_id: str) -> dict:
        self.mission = find_mission(mission_id)
        self.progress = {item["type"]: False for item in self.mission["objectives"]}
        self.elapsed_s = self.distance_m = self.hold_s = 0.0
        self.previous_position = None
        self.last_time_s = None
        self.complete = False
        return self.snapshot()

    @staticmethod
    def _position(state: dict) -> list[float] | None:
        if "position_ned_m" in state:
            p = state["position_ned_m"]
            return [float(p[0]), float(p[1])]
        if "position_enu_m" in state:
            p = state["position_enu_m"]
            return [float(p[0]), float(p[1])]
        return None

    def update(self, state: dict, dt_s: float) -> dict:
        if self.mission is None or self.complete:
            return self.snapshot()
        now = float(state.get("time_s", 0.0))
        dt = max(0.0, min(now-self.last_time_s, 10.0)) if self.last_time_s is not None else 0.0
        self.last_time_s = now
        if state.get("mission_started"):
            self.elapsed_s += dt
            position = self._position(state)
            if position is not None and self.previous_position is not None:
                self.distance_m += math.hypot(position[0]-self.previous_position[0],
                                              position[1]-self.previous_position[1])
            if position is not None:
                self.previous_position = position
        for objective in self.mission["objectives"]:
            kind = objective["type"]
            if self.progress.get(kind, False):
                continue
            altitude = float(state.get("altitude_m", 0.0))
            if kind == "altitude":
                self.progress[kind] = altitude >= objective["value"]
            elif kind == "distance":
                self.progress[kind] = self.distance_m >= objective["value"]
            elif kind == "hold_altitude":
                if state.get("mission_started") and objective["minimum_m"] <= altitude <= objective["maximum_m"]:
                    self.hold_s += dt
                else:
                    self.hold_s = 0.0
                self.progress[kind] = self.hold_s >= objective["seconds"]
            elif kind == "safe_landing":
                touchdown = state.get("mission_metrics", {}).get("touchdown_speed_m_s")
                if touchdown is None and state.get("vehicle") == "space" and state.get("scenario") == "planetary":
                    touchdown = state.get("touchdown_speed_m_s")
                self.progress[kind] = (state.get("phase") == "LANDED" and touchdown is not None
                                       and float(touchdown) <= objective["speed_m_s"])
            elif kind == "rendezvous":
                relative = state.get("relative_position_rtn_m")
                velocity = state.get("relative_velocity_rtn_m_s")
                self.progress[kind] = (relative is not None and velocity is not None
                    and math.sqrt(sum(float(v)**2 for v in relative)) <= objective["range_m"]
                    and math.sqrt(sum(float(v)**2 for v in velocity)) <= objective["speed_m_s"])
        self.complete = all(self.progress.values())
        return self.snapshot()

    def snapshot(self) -> dict:
        if self.mission is None:
            return {"active": False, "mission": None, "progress": {},
                    "elapsed_s": 0.0, "distance_m": 0.0, "hold_s": 0.0,
                    "complete": False}
        return {"active": True, "mission": deepcopy(self.mission),
                "progress": dict(self.progress), "elapsed_s": self.elapsed_s,
                "distance_m": self.distance_m, "hold_s": self.hold_s,
                "complete": self.complete}
