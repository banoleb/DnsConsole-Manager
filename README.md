# DnsConsole-Manager (beta v0.0.2)

✨`I am actively developing the project and will be glad to receive any contribution.`

😎`The project is 99 percent vibe coding and 1 percent my idea.`
*(So, don't throw a brick at me.)*

[logo3]: docs/img/master-logo2.gif "Logo Title Text 2"
[logo4]: docs/img/main-shema.png "Logo Title Text "

## Architecture
![alt text][logo4]

Dnsdist Web-Console-Manager is a  centralized management of multiple dnsdist instances. The project simplifies DNS traffic control, DDoS mitigation, configuration management, and real-time statistics collection across distributed dnsdist deployments.


### API Server Architecture
```
┌─────────────────┐
│ Web-Console     │ (console.py): Flask-based web interface for managing and monitoring API server agents
└────────┬────────┘
         │ JSON Request
         │ {"command": "..."}
         ▼
┌─────────────────┐
│ webapi-agent   │  (webapi-agent.py) (HTTP Server cli proxy)
│                 │
└────────┬────────┘
         │
         │ CLI Console Connection
         ▼
┌─────────────────┐
│   dnsdist       │
│  127.0.0.1:5199 │
└────────┬────────┘
         │ Execute Command
         │
         ▼
    ┌─────────┐
    │ Response│ output back to Web-Console
    └─────────┘
```

## Features

- ✅ Real-time agent status monitoring
- ✅ Interactive command execution interface
- ✅ Background sync of  showRules() and showServers() and etc.
- ✅ Command autocomplete and history
- ✅ Automatic rules synchronization to agents
- ✅ Victoria Metrics integration for agent status, topClients, and topQueries metrics export


![alt text][logo3]
## Quick Start

### Using dnsdist and cli

##### read this https://www.dnsdist.org/guides/console.html

1. Configure dnsdist by including this:

```
controlSocket('127.0.0.1:5199')
setConsoleACL('0.0.0.0/0')
setKey("8ABLRNt6DamXrG/7PhUo2y6x6M2ZUidQfDLfYdTc8gM=")
    # example uses makeKey() in cli
```

2. Start/restart dnsdist:

```bash
systemctl restart dnsdist
```

### Install webapi-agent
#### start agent on the dns-dist host

1. pull project

2. Install Python dependencies:

```bash
pip3 install -r requirements.txt

# for generate token
python3 webapi-agent.py --create_token

# example
# change: app/settings.py
python3 webapi-agent.py --port 8080 --console-host  127.0.0.1 --console-port 5199 --key "YjNUOVRYOXl6OGFKWDRYWGhuQWhYQXlQVzM3UVA0WHk="  --webtoken DLE-GL_SNSlGqegTAsMwNhb07-r2thYmI14mD9BBa-k
```

4. Start via docker-compose:

```bash
# change: docker-compose-agent.yml environments
docker compose -f docker-compose-agent.yml up -d
```

5. Check heath status

```
http://0.0.0.0:8055/api/v1/info
```


### Start Web Console
##### start console on the dns-dist host or on dedicated server or vm

#### 1. Start the Web Console:

##### change: app/settings.py

```bash
# use venv if needed
# python3 -m venv venv
# pip3 install -r requirements.txt
# source venv/bin/activate

pip3 install -r requirements.txt
python3 console.py

# or

gunicorn --workers 4 --bind 0.0.0.0:5000 wsgi:app

```


to start background syncer process:
```
./syncer.sh
```

In docker
```
# change: docker-compose-console.yml environments or .env file
docker compose -f docker-compose-console.yml build
docker compose -f docker-compose-console.yml up -d --remove-orphans
```
**Additional Gunicorn options:**

```bash
# Bind to a specific host and port
gunicorn --workers 4 --bind 127.0.0.1:5000 wsgi:app

# Enable access logging
gunicorn --workers 4 --bind 0.0.0.0:5000 --access-logfile - wsgi:app

# Run as a daemon (background process)
gunicorn --workers 4 --bind 0.0.0.0:5000 --daemon wsgi:app

# Specify a PID file
gunicorn --workers 4 --bind 0.0.0.0:5000 --pid /var/run/gunicorn.pid wsgi:app

# Set worker timeout (useful for long-running commands)
gunicorn --workers 4 --bind 0.0.0.0:5000 --timeout 120 wsgi:app
```


#### 2. Access the web console in your browser:
   - Web Console: http://localhost:5000/



### Seed data
#### For a quick start, you can fill in the database data, add agents and template rules

```bash
# use seed_data.psql.sql for psql
# use seed_data.sqlite.sql for sqlite

# Start console in first - to automatically create a database schema and then load the data
psql -h server-psql -U psql -d psql -f db/seed_data.psql.sql

# or use default db dnsdist_webapi.db in app dir
```



### Environment Variables

#### Console

- `WEBAPI_PORT` - Port for console web interface (default: 5000)
- `WEBAPI_HOST` - Host to bind to (default: 0.0.0.0)
- `DATABASE_URL` - Database connection string (default: sqlite:////data/dnsdist_webapi.db)

#### Agents

- `WEBAPI_PORT` - Port for API server (default: 8080)
- `DNSDIST_CONSOLE_HOST` - DNSDist console host (default: 127.0.0.1)
- `DNSDIST_CONSOLE_PORT` - DNSDist console port (default: 5199)
- `DNSDIST_KEY` - Encryption key for console authentication (**CHANGE IN PRODUCTION**)
- `WEBAPI_TOKEN` - Web API authentication token (**CHANGE IN PRODUCTION**)

#### Monitoring

- `VICTORIA_METRICS_ENABLED` =false
- `VICTORIA_METRICS_HOST` - Victoria Metrics host (default: localhost)
- `VICTORIA_METRICS_PORT` - Victoria Metrics port (default: 8428)
- `VICTORIA_METRICS_URL` - Victoria Metrics URL path (default: /api/v1/import/prometheus)



### Pytest
```
cd app
pytest test_webapi_agent.py -v
pytest test_console.py -v
```


### ChangeLog

#### BETA v0.0.1 28.02.2026
- init project
#### BETA v0.0.2 05.03.2026
- Minor changes, background sync logic fixed. Action buttons added for rules
