# FlixRP Moderation Discord-Bot

<a href="https://discord.flixrp.net"><img src="https://img.shields.io/discord/665677622604201993?color=7289da&logo=discord&logoColor=white" alt="Discord server" /></a>

<hr>

Moderations Discord-Bot von FlixRP.

## Features

### Fraktions-System

Der Fraktions-Chat ist ein Chat in dem Fraktionsmanager Benutzern ihre Fraktionsrolle zuweisen und entfernen können.

#### Konfiguration

Konfigurieren kann man die Fraktionen in `fraktionen-config.json`.

Die Datei hat diesen Grundaufbau:

```json
{
  "log_channel_id": 853727357981687848,
  "faction_chat_id": 866718078573084682,
  "factions": [
    {
      "role": 673306966344466483,
      "ogs": [
        673306978118008865,
        758408692076642354,
        977146479812694056
      ],
      "aliases": [
        "lspd",
        "pd"
      ]
    },
    {
      "role": 758408692076642354,
      "ogs": [
        673306978118008865
      ],
      "aliases": [
        "lspd-stv",
        "pd-stv"
      ]
    }
  ]
}
```

`log_channel_id` ist die Kanal-ID des Fraktions-Logs in dem geloggt wird, wer wem welche Rolle gegeben bzw. entfernt hat.
`faction_chat_id` ist die Kanal-ID des Fraktions-Chats, indem die Benutzer ihre Fraktions-Ränge anfordern.
`factions` ist eine liste mit den Fraktionen.
Jede Fraktion hat hier die Fraktions-Rolle konfiguriert, eine liste der OGs, die den Benutzern die Fraktions-Rolle vergeben können, und den aliasen.

Alle weiteren Attribute die hier nicht beschrieben sind, werden ignoriert!

### Befehle

| Slash Command                | Beschreibung                                                                                                                                                                                                                                                                                                                                                              |
|------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `/userinfo`                  | Detaillierte User-Informationen. Zeigt ob der user auf dem server ist, ob und mit welchem grund er gebannt ist, wie lange er im timeout ist, ob und in welchem sprachkanal er ist, erstellungsdatum des accounts, wann der account beigetreten ist, Die discord aktivität und auf welchen geräten derjenige aktiv ist, seit wann er den server boostet und vieles mehr... |
| `/inviteinfo`                | Zeigt details über eine Einladung an.                                                                                                                                                                                                                                                                                                                                     |
| `/frak-list`                 | Ein Fraktionsleiter kann hier die liste aller Mitglieder ausgeben.                                                                                                                                                                                                                                                                                                        |
| `/sync-category-permissions` | Synchronisiert die Berechtigungen in allen Channeln einer Kategorie mit dieser.                                                                                                                                                                                                                                                                                           |
| `/delete-category-channels`  | Löscht alle Channel in einer Kategorie.                                                                                                                                                                                                                                                                                                                                   |


### Mutes

Mute Befehle fürs Team welche die Timeout Funktion von Discord nutzen.
Moderatoren können diese Befehle zur sicherheit nur einmal pro Minute ausführen.
Die Befehle sind so gemacht, dass man sie von jedem Channel aus ausführen kann ohne das die User davon etwas mitbekommen. Eine Log-Nachricht wird anschließend in einen konfigurierten Channel gesendet.

| Slash Command | Beschreibung                                                                                                            |
|---------------|-------------------------------------------------------------------------------------------------------------------------|
| `/mute`       | Um leute in den Timeout zu schicken. Mit dem Discord Timeout kann man nirgends mehr schreiben und auch nicht reagieren. |
| `/unmute`     | Entfernt jemandem den timeout.                                                                                          |

### Nachrichten löschen

Der bot hat einen context-menü Befehl um Nachrichten zu löschen. Die zu löschende Nachricht wird vorher in einen Log-Channel gesendet.

### Bans

| Slash Command | Beschreibung                                                                                                                            |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| `/unban`      | Entbannt einen User und sendet eine log-Nachricht. Der entbannte User wird zusätzlich in der Datenbank gespeichert.                     |
| `/ban`        | Bannt einen Spieler. Dabei werden die Rollen die der Benutzer hatte gespeichert um den Ban später leichter rückgängig machen zu können. |

### Verbotene namen

Wenn ein benutzer beitritt oder seinen Namen ändert, und dieser gleich ist wie einer in der Konfiguration einstellten Namen, wird der Benutzer gekickt und eine Log-Nachricht wird gesendet.
Die Namen der Benutzer werden dabei mit dem package `unidecode` geprüft und Sonderschriftzeichen werden zu normalen ascii Zeichen ersetzt.
So werden auch Benutzer mit einem Namen in Frakturschrift erkannt.

## Abhängigkeiten:

- Datenbank Management System: mariadb oder mysql.
- Python3.8 oder höher.
- Siehe `requirements.txt` für die benötigten python pakete.

Die python pakete können global mit `pip3 install -r requirements.txt` installiert werden oder in einem Virtuellen environment wie folgt:

```shell
# setup virtual environment
python3 -m venv venv
# install python packages into the virtual environment
./venv/bin/pip3 install -r requirements.txt
# run the bot
./venv/bin/python3 bot.py
```

## Setup

Der Bot braucht den Member-Intent eingeschalten im [Discord Developer Portal](https://discord.com/developers/applications).

1. Erstelle Datenbank Tabellen mithilfe der `reset.sql`.
2. `config.ini.dist` kopieren zu `config.ini`.
3. Konfiguriere `config.ini`.
4. Starte `bot.py`. Unter Linux beispielweise so: `python3 bot.py`. Oder mit `./venv/bin/python3 bot.py` wenn du ein environment eingerichtet hast.

## Systemctl

Beispiel .service Datei:

```ini
[Unit]
Description=Moderation Discord Bot for ForgeRP
After=network.target

[Service]
WorkingDirectory=/path_to_project
ExecStart=/path_to_project/venv/bin/python3 bot.py
Type=simple
Restart=always
User=flix_bot

[Install]
WantedBy=multi-user.target
```