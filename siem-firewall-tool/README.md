# SIEM Firewall Tool

A lightweight SIEM tool built in Python and Flask that collects firewall logs, generates alerts, and shows a live dashboard.

## Features
- Log parsing from `ufw.log`
- Real-time alerts (port scans, brute force, etc.)
- Dashboard with logs, alerts, and traffic graph
- Auto-restart services with `setup.sh`

## Setup
```bash
git clone https://github.com/GouravSingh97/siem-firewall-tool.git
cd siem-firewall-tool
./setup.sh
