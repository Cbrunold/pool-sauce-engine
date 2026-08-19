# Running Pool Sauce Engine on your phone (beta)

Your phone and PC must be on the **same WiFi** (`Livebox-211C`).

The app runs in WSL2, which has a private network. We bridge **one port (5173)**
from Windows to WSL. The Vite dev server proxies `/api` to the backend
internally, so only 5173 needs exposing.

## Addresses
- Phone opens: **http://192.168.1.29:5173**
- Windows LAN IP: `192.168.1.29`
- WSL internal IP: `172.29.253.75` (⚠ can change when WSL/PC restarts — see below)

---

## One-time setup (elevated PowerShell — "Run as administrator")

```powershell
$wsl = (wsl -d Ubuntu hostname -I).Trim().Split()[0]
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=5173 connectaddress=$wsl connectport=5173
New-NetFirewallRule -DisplayName "PSE Vite 5173" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
```

Then on your phone, open **http://192.168.1.29:5173**

---

## Start the servers (two WSL terminals, or background)

**Backend (FastAPI):**
```bash
cd ~/code/pool-sauce-engine
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Frontend (Vite):**
```bash
source ~/.nvm/nvm.sh
cd ~/code/pool-sauce-engine/web
npm run dev -- --host 0.0.0.0
```

---

## After a reboot — WSL IP changes, refresh the proxy (elevated PowerShell)

```powershell
$wsl = (wsl -d Ubuntu hostname -I).Trim().Split()[0]
netsh interface portproxy reset
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=5173 connectaddress=$wsl connectport=5173
```

---

## Cleaner alternative: WSL mirrored networking (survives reboots, no portproxy)

Create/edit `C:\Users\charl\.wslconfig`:
```ini
[wsl2]
networkingMode=mirrored
```
Then `wsl --shutdown`, reopen WSL, restart both servers. Now the phone can reach
`http://192.168.1.29:5173` directly with no portproxy and no per-reboot refresh.

---

## Teardown (remove the bridge, elevated PowerShell)

```powershell
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=5173
Remove-NetFirewallRule -DisplayName "PSE Vite 5173"
```

---

## Quick test checklist
1. Phone loads the **RŌ** capture screen.
2. **Place Balls Manually** → tap table → pick ball ids (cue + a couple object balls).
3. **Confirm Layout** → Table screen → tap a pocket → **Compute Shot**.
4. Shot screen shows: The Path (with colored landing cone), The Cut (aiming card),
   Position, The Sauce.
5. **Shot Taken** → tap where cue landed → **Submit Debrief** → Pillar V.
