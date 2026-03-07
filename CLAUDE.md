# Cash Mashine

Antworte immer auf Deutsch.

## Projektbeschreibung
Multi-Agenten-System das parallel im Internet nach Geldverdien-Ideen sucht.
Mehrere KI-Agenten "rennen" gleichzeitig und der Beste Vorschlag gewinnt.
Die siegreiche Idee wird automatisch mit einem konkreten Umsetzungsplan ausgestattet.

## Architektur

```
cash mashine/
├── agents/          — 6 spezialisierte Geld-Agenten
│   ├── base_agent.py       BaseMoneyAgent + MoneyIdea Datenklasse
│   ├── survey_agent.py     Bezahlte Umfragen
│   ├── airdrop_agent.py    Krypto-Airdrops
│   ├── gift_agent.py       Freebies, Gratis-Produkte
│   ├── cashback_agent.py   Cashback & Rewards
│   ├── passive_agent.py    Passives Einkommen
│   └── gig_agent.py        Gig Economy, Micro-Tasks
├── core/            — Kern-Logik
│   ├── race_engine.py      Orchestriert das Rennen (asyncio parallel)
│   ├── scorer.py           Bewertet Ideen (gewichtetes Scoring)
│   ├── brain.py            Entscheidet Gewinner + Umsetzungsplan
│   └── control_center.py   Live-Dashboard aller Agenten
├── state/           — Persistenz
│   ├── ideas.json          Alle gefundenen Ideen (letzte Runde)
│   ├── race_results.json   Rennen-Historie
│   ├── brain_state.json    Aktueller Gewinner + Plan
│   └── control_center.json Agenten-Status
└── logs/            — Logs
```

## Tech Stack
- Python 3.12
- OpenAI API (gpt-4o-mini fuer Agenten, gpt-4o fuer Brain)
- asyncio fuer parallele Ausfuehrung
- requests + BeautifulSoup4 fuer Web-Scraping

## Start
```
1_START.bat        — Ein einzelnes Rennen
2_DAUERLAUF.bat    — Kontinuierlicher Betrieb (alle 60 Min)
3_RENNEN_3X.bat    — 3 Rennen, dann Pause
4_STATUS.bat       — Status und Historie anzeigen
5_STOP.bat         — Dauerlauf stoppen
```

## Scoring-Formel
```
raw_score = (
    0.35 * earnings_score     # Monatliches Potenzial (log-normalisiert)
  + 0.25 * reliability        # Vertrauenswuerdigkeit
  + 0.20 * speed              # Wie schnell kommt Geld?
  + 0.20 * efficiency         # EUR pro Stunde Aufwand
)
```

## Patterns (aus MarketingBot gelernt)
- Brain: Observe → Decide → Implement → Reflect → Adapt
- PlanLoop: analyze → plan → implement → verify → report
- ControlCenter: Aggregierter Live-Status aller Agenten
- Dauerlauf: Endlosschleife mit Signal-Handler und Lock-File

## Erweiterungen
- Neuen Agenten hinzufuegen: agents/ Ordner, erbt von BaseMoneyAgent
- Scoring anpassen: core/scorer.py Gewichte aendern
- Modell wechseln: config.json -> model / model_brain
- OpenRouter nutzen: Alternativer Client in main.py

## Regeln
- API Keys NUR in .env, niemals im Code
- Config in config.json anpassen (nicht im Code)
- Neue Agenten muessen BaseMoneyAgent erben
- Kategorie-Namen: survey | airdrop | gift | cashback | passive | gig
